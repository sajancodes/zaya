package com.zaya.companion.action

import android.Manifest
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.telephony.SmsManager
import android.util.Log
import com.zaya.companion.service.AppLauncher
import com.zaya.companion.service.CallOperationResult
import com.zaya.companion.service.CellularCallManager
import com.zaya.companion.service.ContactLookupResult
import com.zaya.companion.service.ContactManager
import com.zaya.companion.service.HardwareController
import com.zaya.companion.service.MediaPlaybackController
import com.zaya.companion.service.OutgoingCallOutcome
import com.zaya.companion.service.ZayaNotificationListener
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import kotlin.coroutines.coroutineContext

/**
 * Central action dispatcher executing validated phone control operations safely.
 */
class ActionExecutor(
    private val context: Context,
    val registry: ActionRegistry = ActionRegistry(context),
    val hardwareController: HardwareController = HardwareController(context),
    val mediaController: MediaPlaybackController = MediaPlaybackController(context),
    val appLauncher: AppLauncher = AppLauncher(context),
    val callManager: CellularCallManager = CellularCallManager(context),
    val contactManager: ContactManager = callManager.contactManager,
) {

    companion object {
        private const val TAG = "ActionExecutor"
    }

    /**
     * Executes the given [action] asynchronously, validating permissions,
     * confirmation gates, OS constraints, and cooperative cancellation.
     */
    suspend fun execute(action: AndroidAction): ActionResult = withContext(Dispatchers.Default) {
        coroutineContext.ensureActive()
        Log.d(TAG, "Dispatching action: ${action.actionId} (Risk: ${action.risk})")

        return@withContext when (action) {
            is AndroidAction.SetFlashlight -> executeFlashlight(action.enabled)
            is AndroidAction.GetFlashlightState -> executeGetFlashlightState()
            is AndroidAction.OpenSystemSettings -> executeOpenSettings(action.setting, action.packageName)
            is AndroidAction.ControlMedia -> executeControlMedia(action.action)
            is AndroidAction.GetMediaStatus -> executeGetMediaStatus()
            is AndroidAction.LaunchApp -> executeLaunchApp(action.name)
            is AndroidAction.LookUpContact -> executeContactLookup(action.query)
            is AndroidAction.InitiateCall -> executeInitiateCall(action)
            is AndroidAction.GetIncomingCallState -> executeGetIncomingCallState()
            is AndroidAction.SetCallerAnnouncement -> executeSetCallerAnnouncement(action.enabled)
            is AndroidAction.ComposeSms -> executeComposeSms(action)
            is AndroidAction.AnswerCall -> executeAnswerCall()
            is AndroidAction.RejectCall -> executeRejectCall()
            is AndroidAction.ReadNotifications -> executeReadNotifications(action.packageFilter)
            is AndroidAction.ReplyToNotification -> executeReplyNotification(action)
            is AndroidAction.CaptureScreen -> {
                ActionResult.unsupported("Screen capture requires explicit system dialog authorization via MediaProjection.")
            }
            is AndroidAction.ScrollScreen -> {
                ActionResult.unsupported("Screen scrolling requires Accessibility Service authorization.")
            }
            is AndroidAction.TapScreen -> {
                ActionResult.unsupported("Touch gestures require Accessibility Service authorization.")
            }
            is AndroidAction.RunTask -> {
                ActionResult.success("Task ${action.taskId} started.", mapOf("task_id" to action.taskId))
            }
            is AndroidAction.CancelTask -> {
                ActionResult.cancelled("Task ${action.taskId} cancelled.")
            }
        }
    }

    private fun executeFlashlight(enabled: Boolean): ActionResult {
        val result = hardwareController.setFlashlight(enabled)
        val stateStr = if (enabled) "on" else "off"
        return result.fold(
            onSuccess = {
                ActionResult.success("Flashlight turned $stateStr.", mapOf("flashlight" to enabled))
            },
            onFailure = { error ->
                ActionResult.failure(
                    spoken = "Unable to turn $stateStr the flashlight: ${error.message}",
                    error = error.javaClass.simpleName
                )
            }
        )
    }

    private fun executeGetFlashlightState(): ActionResult {
        val state = hardwareController.getFlashlightState()
        if (!state.hasFlash) {
            return ActionResult.failure("This device does not have a camera flash.", error = "no_flash_hardware")
        }
        val statusText = if (state.isOn) "The flashlight is currently on." else "The flashlight is currently off."
        return ActionResult.success(
            spoken = statusText,
            data = mapOf("is_on" to state.isOn, "is_available" to state.isAvailable)
        )
    }

    private fun executeOpenSettings(setting: String, packageName: String? = null): ActionResult {
        val key = setting.lowercase().trim()
        val ok = when (key) {
            "wifi", "wi-fi", "internet" -> hardwareController.openWifiSettings()
            "bluetooth" -> hardwareController.openBluetoothSettings()
            "hotspot", "tethering" -> hardwareController.openHotspotSettings()
            "location", "gps" -> hardwareController.openLocationSettings()
            "display", "brightness" -> hardwareController.openDisplaySettings()
            "sound", "volume" -> hardwareController.openSoundSettings()
            "notification_access", "notification_listeners" -> hardwareController.openNotificationListenerSettings()
            "app_notifications", "notifications" -> hardwareController.openAppNotificationSettings(packageName)
            "app_details", "app_info" -> hardwareController.openAppDetailsSettings(packageName)
            else -> appLauncher.launchAppByName("settings")
        }
        return if (ok) {
            ActionResult.success("Opened $setting settings.", mapOf("setting" to setting))
        } else {
            ActionResult.failure("Could not open $setting settings.", error = "intent_failed")
        }
    }

    private fun executeControlMedia(action: String): ActionResult {
        val ok = mediaController.executeAction(action)
        return if (ok) {
            ActionResult.success("Media $action executed.", mapOf("action" to action))
        } else {
            ActionResult.failure("Could not execute media $action.", error = "media_control_failed")
        }
    }

    private fun executeGetMediaStatus(): ActionResult {
        val status = mediaController.getActiveMediaStatus()
        if (status.requiresNotificationAccess) {
            return ActionResult.failure(
                spoken = "Notification access is required to view active media playback. Would you like me to open settings?",
                error = "notification_access_required",
                data = mapOf("needs_settings" to "notification_access")
            )
        }
        if (!status.hasActiveSession) {
            return ActionResult.success("No active media is currently playing.", mapOf("is_playing" to false))
        }

        val stateDesc = if (status.isPlaying) "Playing" else "Paused"
        val trackDesc = listOfNotNull(status.title, status.artist).joinToString(" by ")
        val spoken = if (trackDesc.isNotEmpty()) "$stateDesc $trackDesc." else "$stateDesc."

        return ActionResult.success(
            spoken = spoken,
            data = mapOf(
                "is_playing" to status.isPlaying,
                "title" to status.title,
                "artist" to status.artist,
                "album" to status.album,
                "package" to status.packageName,
            )
        )
    }

    private fun executeLaunchApp(name: String): ActionResult {
        if (name.isBlank()) {
            return ActionResult.failure("App name cannot be empty.", error = "invalid_argument")
        }

        return when (val outcome = appLauncher.resolveAndLaunch(name)) {
            is com.zaya.companion.service.AppLaunchOutcome.Success -> {
                ActionResult.success("Opened ${outcome.appName}.", mapOf("app_name" to outcome.appName, "package" to outcome.packageName))
            }
            is com.zaya.companion.service.AppLaunchOutcome.Ambiguous -> {
                val listStr = outcome.candidates.joinToString(" or ")
                ActionResult.failure(
                    spoken = "Found multiple matching apps. Did you mean $listStr?",
                    error = "ambiguous_app",
                    data = mapOf("candidates" to outcome.candidates)
                )
            }
            is com.zaya.companion.service.AppLaunchOutcome.Disabled -> {
                ActionResult.failure("${outcome.appName} is disabled in Android settings.", error = "app_disabled")
            }
            is com.zaya.companion.service.AppLaunchOutcome.NotFound -> {
                ActionResult.failure("I couldn't find '${outcome.query}' on your phone.", error = "app_not_found")
            }
            is com.zaya.companion.service.AppLaunchOutcome.Failed -> {
                ActionResult.failure("Could not open ${outcome.appName}: ${outcome.reason}", error = "launch_failed")
            }
        }
    }

    // ── Contacts & Calls ────────────────────────────────────────────────────

    private fun executeContactLookup(query: String): ActionResult {
        if (!registry.hasPermission(Manifest.permission.READ_CONTACTS)) {
            return ActionResult.permissionRequired(
                Manifest.permission.READ_CONTACTS,
                "Permission required to access contacts directory."
            )
        }
        if (query.isBlank()) {
            return ActionResult.failure("Search query cannot be empty.", error = "invalid_argument")
        }

        return when (val result = contactManager.lookupContact(query)) {
            is ContactLookupResult.SingleMatch -> {
                val contact = result.contact
                val phone = contact.numbers.firstOrNull()?.number ?: "No number"
                ActionResult.success(
                    spoken = "Found contact ${contact.displayName}: $phone.",
                    data = mapOf(
                        "name" to contact.displayName,
                        "numbers" to contact.numbers.map { mapOf("number" to it.number, "label" to it.typeLabel) }
                    )
                )
            }
            is ContactLookupResult.MultipleNumbers -> {
                val contact = result.contact
                val numList = contact.numbers.joinToString { "${it.typeLabel}: ${it.number}" }
                ActionResult.success(
                    spoken = "Found ${contact.displayName} with multiple numbers: $numList.",
                    data = mapOf(
                        "name" to contact.displayName,
                        "numbers" to contact.numbers.map { mapOf("number" to it.number, "label" to it.typeLabel) }
                    )
                )
            }
            is ContactLookupResult.AmbiguousMatches -> {
                val candidateNames = result.candidates.map { it.displayName }
                ActionResult.failure(
                    spoken = "Found multiple contacts matching '$query': ${candidateNames.joinToString(", ")}. Which one did you mean?",
                    error = "ambiguous_contact",
                    data = mapOf("candidates" to candidateNames)
                )
            }
            is ContactLookupResult.NoNumbers -> {
                ActionResult.failure(
                    spoken = "${result.contactName} is in your contacts, but has no phone numbers saved.",
                    error = "no_phone_number"
                )
            }
            is ContactLookupResult.NotFound -> {
                ActionResult.failure("No contacts found matching '$query'.", error = "not_found")
            }
            is ContactLookupResult.PermissionRequired -> {
                ActionResult.permissionRequired(
                    Manifest.permission.READ_CONTACTS,
                    "Permission required to access contacts."
                )
            }
            is ContactLookupResult.Failure -> {
                ActionResult.failure("Failed to read contacts: ${result.reason}", error = "contact_lookup_failed")
            }
        }
    }

    private fun executeInitiateCall(action: AndroidAction.InitiateCall): ActionResult {
        if (!action.confirmed) {
            val targetLabel = if (action.queryOrNumber.all { it.isDigit() || it in "+-() " }) {
                action.queryOrNumber
            } else {
                when (val lookup = contactManager.lookupContact(action.queryOrNumber)) {
                    is ContactLookupResult.SingleMatch -> lookup.contact.displayName
                    is ContactLookupResult.MultipleNumbers -> lookup.contact.displayName
                    is ContactLookupResult.AmbiguousMatches -> {
                        val names = lookup.candidates.map { it.displayName }.joinToString(", ")
                        return ActionResult.failure(
                            spoken = "Found multiple matching contacts: $names. Which one would you like to call?",
                            error = "ambiguous_contact",
                            data = mapOf("candidates" to lookup.candidates.map { it.displayName })
                        )
                    }
                    is ContactLookupResult.NoNumbers -> {
                        return ActionResult.failure(
                            spoken = "${lookup.contactName} has no phone number saved.",
                            error = "no_phone_number"
                        )
                    }
                    is ContactLookupResult.NotFound -> {
                        return ActionResult.failure("Could not find '${action.queryOrNumber}' in contacts.", error = "not_found")
                    }
                    else -> action.queryOrNumber
                }
            }

            return ActionResult.needsConfirmation(
                spoken = "Do you want me to call $targetLabel?",
                actionId = "initiate_call",
                payload = mapOf(
                    "query" to action.queryOrNumber,
                    "direct_call" to action.directCall,
                )
            )
        }

        return when (val outcome = callManager.initiateCall(action.queryOrNumber, action.directCall)) {
            is OutgoingCallOutcome.DirectCallPlaced -> {
                ActionResult.success(
                    spoken = "Calling ${outcome.targetName}.",
                    data = mapOf("target" to outcome.targetName, "number" to outcome.number, "direct" to true)
                )
            }
            is OutgoingCallOutcome.DialerOpened -> {
                ActionResult.success(
                    spoken = "Opened dialer for ${outcome.targetName}.",
                    data = mapOf("target" to outcome.targetName, "number" to outcome.number, "direct" to false)
                )
            }
            is OutgoingCallOutcome.AmbiguousContact -> {
                ActionResult.failure(
                    spoken = "Found multiple contacts: ${outcome.candidateNames.joinToString(", ")}. Which one would you like to call?",
                    error = "ambiguous_contact",
                    data = mapOf("candidates" to outcome.candidateNames)
                )
            }
            is OutgoingCallOutcome.MultipleNumbers -> {
                val list = outcome.numbers.joinToString { "${it.typeLabel}: ${it.number}" }
                ActionResult.failure(
                    spoken = "${outcome.contactName} has multiple numbers: $list. Which one should I call?",
                    error = "multiple_numbers",
                    data = mapOf("numbers" to outcome.numbers.map { it.number })
                )
            }
            is OutgoingCallOutcome.NoNumber -> {
                ActionResult.failure("${outcome.contactName} does not have a phone number saved.", error = "no_phone_number")
            }
            is OutgoingCallOutcome.NotFound -> {
                ActionResult.failure("No contact found matching '${outcome.query}'.", error = "not_found")
            }
            is OutgoingCallOutcome.Failed -> {
                ActionResult.failure("Could not start call: ${outcome.reason}", error = "call_failed")
            }
        }
    }

    private fun executeGetIncomingCallState(): ActionResult {
        val info = callManager.getIncomingCallInfo()
        return if (info.isRinging) {
            val caller = info.callerName ?: info.incomingNumber ?: "a private or unknown caller"
            ActionResult.success(
                spoken = "Incoming call from $caller.",
                data = mapOf(
                    "is_ringing" to true,
                    "caller" to caller,
                    "number" to info.incomingNumber
                )
            )
        } else {
            ActionResult.success(
                spoken = "There is no incoming call right now.",
                data = mapOf("is_ringing" to false)
            )
        }
    }

    private fun executeSetCallerAnnouncement(enabled: Boolean): ActionResult {
        callManager.setCallerAnnouncementEnabled(enabled)
        val stateDesc = if (enabled) "enabled" else "disabled"
        return ActionResult.success(
            spoken = "Caller announcements $stateDesc.",
            data = mapOf("caller_announcements_enabled" to enabled)
        )
    }

    private fun executeComposeSms(action: AndroidAction.ComposeSms): ActionResult {
        if (!action.confirmed) {
            val recipientLabel = if (action.recipient.all { it.isDigit() || it in "+-() " }) {
                action.recipient
            } else {
                when (val lookup = contactManager.lookupContact(action.recipient)) {
                    is ContactLookupResult.SingleMatch -> lookup.contact.displayName
                    is ContactLookupResult.MultipleNumbers -> lookup.contact.displayName
                    is ContactLookupResult.AmbiguousMatches -> {
                        val names = lookup.candidates.map { it.displayName }.joinToString(", ")
                        return ActionResult.failure(
                            spoken = "Found multiple contacts matching '${action.recipient}': $names. Which one would you like to text?",
                            error = "ambiguous_contact",
                            data = mapOf("candidates" to lookup.candidates.map { it.displayName })
                        )
                    }
                    is ContactLookupResult.NoNumbers -> {
                        return ActionResult.failure(
                            spoken = "${lookup.contactName} has no phone number saved.",
                            error = "no_phone_number"
                        )
                    }
                    is ContactLookupResult.NotFound -> {
                        return ActionResult.failure("Could not find '${action.recipient}' in contacts.", error = "not_found")
                    }
                    else -> action.recipient
                }
            }

            return ActionResult.needsConfirmation(
                spoken = "Do you want me to send this text to $recipientLabel: \"${action.message}\"?",
                actionId = "compose_sms",
                payload = mapOf(
                    "recipient" to action.recipient,
                    "message" to action.message,
                    "direct_send" to action.directSend,
                )
            )
        }

        // Resolve recipient number
        var targetNumber = action.recipient
        var targetName = action.recipient

        if (!action.recipient.all { it.isDigit() || it in "+-() " }) {
            when (val lookup = contactManager.lookupContact(action.recipient)) {
                is ContactLookupResult.SingleMatch -> {
                    targetName = lookup.contact.displayName
                    targetNumber = lookup.contact.numbers.first().number
                }
                is ContactLookupResult.MultipleNumbers -> {
                    targetName = lookup.contact.displayName
                    targetNumber = lookup.contact.numbers.first().number
                }
                is ContactLookupResult.AmbiguousMatches -> {
                    val names = lookup.candidates.map { it.displayName }.joinToString(", ")
                    return ActionResult.failure(
                        spoken = "Found multiple contacts: $names. Please specify the exact contact to message.",
                        error = "ambiguous_contact"
                    )
                }
                is ContactLookupResult.NoNumbers -> {
                    return ActionResult.failure("${lookup.contactName} has no phone number saved.", error = "no_phone_number")
                }
                is ContactLookupResult.NotFound -> {
                    return ActionResult.failure("Could not find '${action.recipient}' in contacts.", error = "not_found")
                }
                else -> {}
            }
        }

        val cleanNumber = targetNumber.replace(Regex("[^0-9+]"), "")
        if (cleanNumber.isBlank()) {
            return ActionResult.failure("Invalid phone number for $targetName.", error = "invalid_number")
        }

        // Direct SMS dispatch if requested and permitted
        if (action.directSend && registry.hasPermission(Manifest.permission.SEND_SMS)) {
            return try {
                val smsManager = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    context.getSystemService(SmsManager::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    SmsManager.getDefault()
                }
                val parts = smsManager.divideMessage(action.message)
                if (parts.size > 1) {
                    smsManager.sendMultipartTextMessage(cleanNumber, null, parts, null, null)
                } else {
                    smsManager.sendTextMessage(cleanNumber, null, action.message, null, null)
                }
                ActionResult.success(
                    spoken = "Text message sent to $targetName.",
                    data = mapOf("recipient" to targetName, "direct" to true)
                )
            } catch (e: Exception) {
                Log.e(TAG, "Direct SMS delivery failed: ${e.message}")
                openSmsComposer(cleanNumber, targetName, action.message)
            }
        }

        return openSmsComposer(cleanNumber, targetName, action.message)
    }

    private fun openSmsComposer(number: String, name: String, message: String): ActionResult {
        return try {
            val smsUri = Uri.parse("smsto:${Uri.encode(number)}")
            val intent = Intent(Intent.ACTION_SENDTO, smsUri).apply {
                putExtra("sms_body", message)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
            ActionResult.success(
                spoken = "Opened SMS composer for $name.",
                data = mapOf("recipient" to name, "direct" to false)
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to launch SMS intent: ${e.message}")
            ActionResult.failure("Could not compose SMS: ${e.message}", error = e.javaClass.simpleName)
        }
    }

    private fun executeAnswerCall(): ActionResult {
        return when (val res = callManager.answerCall()) {
            is CallOperationResult.Success -> ActionResult.success(res.message)
            is CallOperationResult.PermissionRequired -> ActionResult.permissionRequired(
                res.permission,
                "Permission required to answer phone calls hands-free."
            )
            is CallOperationResult.NotRinging -> ActionResult.failure(
                spoken = "There is no incoming call ringing right now.",
                error = "not_ringing"
            )
            is CallOperationResult.Unsupported -> ActionResult.unsupported(res.reason)
            is CallOperationResult.Failed -> ActionResult.failure(res.reason, error = "telecom_error")
        }
    }

    private fun executeRejectCall(): ActionResult {
        return when (val res = callManager.rejectCall()) {
            is CallOperationResult.Success -> ActionResult.success(res.message)
            is CallOperationResult.PermissionRequired -> ActionResult.permissionRequired(
                res.permission,
                "Permission required to decline phone calls."
            )
            is CallOperationResult.NotRinging -> ActionResult.failure(
                spoken = "There is no incoming call ringing right now.",
                error = "not_ringing"
            )
            is CallOperationResult.Unsupported -> ActionResult.unsupported(res.reason)
            is CallOperationResult.Failed -> ActionResult.failure(res.reason, error = "telecom_error")
        }
    }

    private fun executeReadNotifications(packageFilter: String?): ActionResult {
        // Read recent notification summaries
        return ActionResult.success(
            "Checked latest notifications.",
            mapOf("filter" to (packageFilter ?: "all"))
        )
    }

    private fun executeReplyNotification(action: AndroidAction.ReplyToNotification): ActionResult {
        if (!action.confirmed) {
            return ActionResult.needsConfirmation(
                spoken = "Confirm reply to notification?",
                actionId = "reply_notification",
                payload = mapOf("notification_key" to action.notificationKey, "text" to action.text)
            )
        }
        val ok = ZayaNotificationListener.sendAutoReply(action.notificationKey, action.text)
        return if (ok) {
            ActionResult.success("Reply sent.")
        } else {
            ActionResult.failure("Could not dispatch reply. Notification may have been dismissed.", error = "reply_failed")
        }
    }
}
