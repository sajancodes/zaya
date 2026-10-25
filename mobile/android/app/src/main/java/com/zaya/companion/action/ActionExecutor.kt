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
import com.zaya.companion.service.NotificationItem
import com.zaya.companion.service.OutgoingCallOutcome
import com.zaya.companion.service.ReplyOutcome
import com.zaya.companion.service.ScreenCaptureManager
import com.zaya.companion.service.ScreenFrameResult
import com.zaya.companion.service.VisualAnalysis
import com.zaya.companion.service.ZayaNotificationListener
import com.zaya.companion.service.ZayaInteractionService
import com.zaya.companion.service.ScrollOutcome
import com.zaya.companion.service.TapOutcome
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import kotlin.coroutines.coroutineContext

import java.util.concurrent.ConcurrentHashMap

/**
 * Idempotency safeguard preventing accidental duplicate dispatch of sensitive
 * consequential actions (e.g. rapid double-taps, network retries, or replayed events).
 */
class ConsequentialActionDeduplicator(private val windowMillis: Long = 10_000L) {
    private val recentExecutions = ConcurrentHashMap<String, Long>()

    fun isDuplicate(signature: String, now: Long = System.currentTimeMillis()): Boolean {
        recentExecutions.entries.removeIf { now - it.value > windowMillis * 2 }
        val last = recentExecutions[signature] ?: return false
        return (now - last) < windowMillis
    }

    fun record(signature: String, now: Long = System.currentTimeMillis()) {
        recentExecutions[signature] = now
    }

    fun clear() {
        recentExecutions.clear()
    }
}

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
    val screenCaptureManager: ScreenCaptureManager = ScreenCaptureManager(context),
    val memoryStore: com.zaya.companion.memory.PersonalMemoryStore = com.zaya.companion.memory.PersonalMemoryStore(context),
    val deduplicator: ConsequentialActionDeduplicator = ConsequentialActionDeduplicator(),
    val systemUtils: com.zaya.companion.service.SystemUtilitiesController = com.zaya.companion.service.SystemUtilitiesController(context),
) {
    val taskCoordinator: TaskCoordinator by lazy { TaskCoordinator(this) }

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
            is AndroidAction.ReadNotifications -> executeReadNotifications(action.packageFilter, action.limit)
            is AndroidAction.ReadLatestNotification -> executeReadLatestNotification(action.packageFilter)
            is AndroidAction.SummarizeNotifications -> executeSummarizeNotifications(action.packageFilter)
            is AndroidAction.DraftNotificationReply -> executeDraftNotificationReply(action)
            is AndroidAction.ReplyToNotification -> executeReplyNotification(action)
            is AndroidAction.CaptureScreen -> executeCaptureScreen()
            is AndroidAction.DescribeScreen -> executeDescribeScreen(action)
            is AndroidAction.ExtractVisibleText -> executeExtractVisibleText(action)
            is AndroidAction.SummarizeScreen -> executeSummarizeScreen(action)
            is AndroidAction.ScrollScreen -> executeScrollScreen(action)
            is AndroidAction.TapScreen -> executeTapScreen(action)
            is AndroidAction.RunTask -> executeRunTask(action)
            is AndroidAction.CancelTask -> executeCancelTask(action)
            is AndroidAction.PlanAndExecuteTask -> executePlanAndExecuteTask(action)
            is AndroidAction.RememberMemory -> executeRememberMemory(action)
            is AndroidAction.ForgetMemory -> executeForgetMemory(action)
            is AndroidAction.QueryMemory -> executeQueryMemory(action)
            is AndroidAction.EvaluateMath -> executeEvaluateMath(action)
            is AndroidAction.GetDeviceDiagnostics -> executeGetDeviceDiagnostics()
            is AndroidAction.WebSearch -> executeWebSearch(action)
            is AndroidAction.GetWeather -> executeGetWeather(action)
            is AndroidAction.GetDailyBriefing -> executeGetDailyBriefing()
            is AndroidAction.SetTimer -> executeSetTimer(action)
            is AndroidAction.SetAlarm -> executeSetAlarm(action)
            is AndroidAction.GetClipboard -> executeGetClipboard()
            is AndroidAction.SetClipboard -> executeSetClipboard(action)
            is AndroidAction.SendWhatsAppMessage -> executeSendWhatsAppMessage(action)
            is AndroidAction.InspectStorage -> executeInspectStorage(action)
            is AndroidAction.SetVolume -> executeSetVolume(action)
            is AndroidAction.SetRingerMode -> executeSetRingerMode(action)
            is AndroidAction.ExecutePcCommand -> executeExecutePcCommand(action)
            is AndroidAction.ConvertCurrency -> executeConvertCurrency(action)
            is AndroidAction.ReadFile -> executeReadFile(action)
            is AndroidAction.WriteFile -> executeWriteFile(action)
            is AndroidAction.Think -> executeThink(action)
            is AndroidAction.LookupKnowledge -> executeLookupKnowledge(action)
            AndroidAction.NavigateBack -> executeNavigateBack()
            AndroidAction.NavigateHome -> executeNavigateHome()
            AndroidAction.CloseOverlay -> executeCloseOverlay()
            is AndroidAction.NavigateReel -> executeNavigateReel(action)
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
        val cleanAction = action.lowercase(java.util.Locale.ROOT).trim()
        val validMedia = setOf("play", "pause", "play_pause", "toggle", "next", "skip", "previous", "prev", "stop")
        if (cleanAction !in validMedia) {
            return ActionResult.failure(
                spoken = "Unsupported media control action: '$action'. Supported actions are: ${validMedia.joinToString(", ")}.",
                error = "unsupported_media_action"
            )
        }
        val ok = mediaController.executeAction(cleanAction)
        return if (ok) {
            ActionResult.success("Media $cleanAction executed.", mapOf("action" to cleanAction))
        } else {
            ActionResult.failure("Could not execute media $cleanAction.", error = "media_control_failed")
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
        val cleanName = name.trim()
        if (cleanName.isBlank()) {
            return ActionResult.failure("App name cannot be empty.", error = "malformed_parameters")
        }
        if (cleanName.length > 80 || cleanName.contains("\u0000")) {
            return ActionResult.failure("Invalid app name specified.", error = "malformed_parameters")
        }

        val targetName = memoryStore.getAppAlias(cleanName) ?: cleanName
        return when (val outcome = appLauncher.resolveAndLaunch(targetName)) {
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
        val query = action.queryOrNumber.trim()
        if (query.isBlank()) {
            return ActionResult.failure("Call recipient or phone number cannot be blank.", error = "malformed_parameters")
        }
        if (query.length > 80) {
            return ActionResult.failure("Call query or phone number exceeds maximum length.", error = "malformed_parameters")
        }

        if (!action.confirmed) {
            val targetLabel = if (query.all { it.isDigit() || it in "+-() " }) {
                query
            } else {
                when (val lookup = contactManager.lookupContact(query)) {
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
                        return ActionResult.failure("Could not find '$query' in contacts.", error = "not_found")
                    }
                    else -> query
                }
            }

            return ActionResult.needsConfirmation(
                spoken = "Do you want me to call $targetLabel?",
                actionId = "initiate_call",
                payload = mapOf(
                    "query" to query,
                    "direct_call" to action.directCall,
                )
            )
        }

        // Deduplication safety check for confirmed calls
        val callSignature = "initiate_call:${query.lowercase(java.util.Locale.ROOT)}"
        if (deduplicator.isDuplicate(callSignature)) {
            return ActionResult.failure(
                spoken = "Prevented duplicate phone call to '$query' within the safety window.",
                error = "duplicate_consequential_action_prevented",
                data = mapOf("query" to query)
            )
        }
        deduplicator.record(callSignature)

        return when (val outcome = callManager.initiateCall(query, action.directCall)) {
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
        val recipient = action.recipient.trim()
        val message = action.message.trim()

        if (recipient.isBlank()) {
            return ActionResult.failure("SMS recipient cannot be blank.", error = "malformed_parameters")
        }
        if (message.isBlank()) {
            return ActionResult.failure("SMS message cannot be blank.", error = "malformed_parameters")
        }
        if (recipient.length > 80) {
            return ActionResult.failure("SMS recipient query exceeds maximum length.", error = "malformed_parameters")
        }
        if (message.length > 2000) {
            return ActionResult.failure("SMS message exceeds maximum length of 2000 characters.", error = "malformed_parameters")
        }

        if (!action.confirmed) {
            val recipientLabel = if (recipient.all { it.isDigit() || it in "+-() " }) {
                recipient
            } else {
                when (val lookup = contactManager.lookupContact(recipient)) {
                    is ContactLookupResult.SingleMatch -> lookup.contact.displayName
                    is ContactLookupResult.MultipleNumbers -> lookup.contact.displayName
                    is ContactLookupResult.AmbiguousMatches -> {
                        val names = lookup.candidates.map { it.displayName }.joinToString(", ")
                        return ActionResult.failure(
                            spoken = "Found multiple contacts matching '$recipient': $names. Which one would you like to text?",
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
                        return ActionResult.failure("Could not find '$recipient' in contacts.", error = "not_found")
                    }
                    else -> recipient
                }
            }

            return ActionResult.needsConfirmation(
                spoken = "Do you want me to send this text to $recipientLabel: \"$message\"?",
                actionId = "compose_sms",
                payload = mapOf(
                    "recipient" to recipient,
                    "message" to message,
                    "direct_send" to action.directSend,
                )
            )
        }

        // Deduplication safety check for confirmed SMS
        val smsSignature = "compose_sms:${recipient.lowercase(java.util.Locale.ROOT)}:${message.hashCode()}"
        if (deduplicator.isDuplicate(smsSignature)) {
            return ActionResult.failure(
                spoken = "Prevented duplicate SMS to '$recipient' within the safety window.",
                error = "duplicate_consequential_action_prevented",
                data = mapOf("recipient" to recipient)
            )
        }
        deduplicator.record(smsSignature)

        // Resolve recipient number
        var targetNumber = recipient
        var targetName = recipient

        if (!recipient.all { it.isDigit() || it in "+-() " }) {
            when (val lookup = contactManager.lookupContact(recipient)) {
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
                    return ActionResult.failure("Could not find '$recipient' in contacts.", error = "not_found")
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
                val parts = smsManager.divideMessage(message)
                if (parts.size > 1) {
                    smsManager.sendMultipartTextMessage(cleanNumber, null, parts, null, null)
                } else {
                    smsManager.sendTextMessage(cleanNumber, null, message, null, null)
                }
                ActionResult.success(
                    spoken = "Text message sent to $targetName.",
                    data = mapOf("recipient" to targetName, "direct" to true)
                )
            } catch (e: Exception) {
                Log.e(TAG, "Direct SMS delivery encountered an error: ${e.message}")
                val isAmbiguous = e.message?.contains("timeout", ignoreCase = true) == true ||
                    e.message?.contains("radio", ignoreCase = true) == true ||
                    e is SecurityException
                if (isAmbiguous) {
                    ActionResult.failure(
                        spoken = "Message dispatch outcome is uncertain. Please check your messages app to avoid sending twice.",
                        error = "ambiguous_external_outcome",
                        data = mapOf("check_device" to true)
                    )
                } else {
                    openSmsComposer(cleanNumber, targetName, message)
                }
            }
        }

        return openSmsComposer(cleanNumber, targetName, message)
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

    // ── Notifications & Smart Replies ──────────────────────────────────────

    private fun checkNotificationAccess(): Boolean {
        val flat = android.provider.Settings.Secure.getString(
            context.contentResolver,
            "enabled_notification_listeners"
        ) ?: return false
        return flat.contains(context.packageName)
    }

    private fun executeReadNotifications(packageFilter: String?, limit: Int): ActionResult {
        if (!checkNotificationAccess()) {
            return ActionResult.failure(
                spoken = "Notification access is not enabled. Would you like me to open settings so you can grant it?",
                error = "notification_access_disabled",
                data = mapOf("needs_settings" to "notification_listener")
            )
        }

        val items = ZayaNotificationListener.getActiveNotifications(
            context = context,
            packageFilter = packageFilter,
            limit = limit
        )

        if (items.isEmpty()) {
            val spoken = if (!packageFilter.isNullOrBlank()) {
                "You have no new ${packageFilter.replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }} notifications."
            } else {
                "You have no new notifications right now."
            }
            return ActionResult.success(spoken, mapOf("count" to 0, "notifications" to emptyList<Any>()))
        }

        val spokenParts = items.take(4).map { item ->
            val sender = item.title.ifBlank { "Someone" }
            val text = item.text.ifBlank { item.lines.firstOrNull() ?: "sent a message" }
            "$sender on ${item.appName}: \"$text\""
        }

        val spoken = if (items.size == 1) {
            "You have 1 notification: ${spokenParts.first()}."
        } else {
            "You have ${items.size} notifications. ${spokenParts.joinToString(". ")}."
        }

        return ActionResult.success(
            spoken = spoken,
            data = mapOf(
                "count" to items.size,
                "notifications" to items.map {
                    mapOf(
                        "key" to it.key,
                        "app" to it.appName,
                        "package" to it.packageName,
                        "sender" to it.title,
                        "text" to it.text,
                        "can_reply" to it.canReply,
                        "timestamp" to it.timestamp
                    )
                }
            )
        )
    }

    private fun executeReadLatestNotification(packageFilter: String?): ActionResult {
        if (!checkNotificationAccess()) {
            return ActionResult.failure(
                spoken = "Notification access is required to read incoming messages.",
                error = "notification_access_disabled",
                data = mapOf("needs_settings" to "notification_listener")
            )
        }

        val items = ZayaNotificationListener.getActiveNotifications(
            context = context,
            packageFilter = packageFilter,
            limit = 1
        )

        if (items.isEmpty()) {
            val spoken = if (!packageFilter.isNullOrBlank()) {
                "You have no new $packageFilter notifications."
            } else {
                "You have no new notifications right now."
            }
            return ActionResult.success(spoken, mapOf("count" to 0))
        }

        val item = items.first()
        val sender = item.title.ifBlank { "Someone" }
        val body = item.text.ifBlank { item.lines.firstOrNull() ?: "sent a message" }
        val spoken = "Latest notification from $sender on ${item.appName}: \"$body\"."

        return ActionResult.success(
            spoken = spoken,
            data = mapOf(
                "key" to item.key,
                "app" to item.appName,
                "sender" to sender,
                "text" to body,
                "can_reply" to item.canReply,
                "timestamp" to item.timestamp
            )
        )
    }

    private fun executeSummarizeNotifications(packageFilter: String?): ActionResult {
        if (!checkNotificationAccess()) {
            return ActionResult.failure(
                spoken = "Notification access is not enabled.",
                error = "notification_access_disabled",
                data = mapOf("needs_settings" to "notification_listener")
            )
        }

        val items = ZayaNotificationListener.getActiveNotifications(
            context = context,
            packageFilter = packageFilter,
            limit = 25
        )

        if (items.isEmpty()) {
            return ActionResult.success("You have no active notifications to summarize.", mapOf("count" to 0))
        }

        val grouped = items.groupBy { it.appName }
        val summaryPhrases = grouped.map { (app, list) ->
            val senders = list.map { it.title.ifBlank { "Unknown" } }.distinct().take(3).joinToString(", ")
            "${list.size} from $app ($senders)"
        }

        val spoken = "You have ${items.size} notifications: ${summaryPhrases.joinToString("; ")}."
        return ActionResult.success(
            spoken = spoken,
            data = mapOf(
                "total_count" to items.size,
                "apps" to grouped.mapValues { (_, list) -> list.size }
            )
        )
    }

    private fun executeDraftNotificationReply(action: AndroidAction.DraftNotificationReply): ActionResult {
        if (!checkNotificationAccess()) {
            return ActionResult.failure(
                spoken = "Notification access is required to draft replies.",
                error = "notification_access_disabled"
            )
        }

        val item = ZayaNotificationListener.findNotificationForReply(
            context = context,
            targetKey = action.targetKey,
            targetSender = action.targetSender,
            targetPackage = action.targetPackage
        ) ?: return ActionResult.failure(
            spoken = "No active notification found to draft a reply for.",
            error = "notification_not_found"
        )

        // Generate contextual response
        val draft = when {
            !action.contextInstruction.isNullOrBlank() -> action.contextInstruction
            item.text.endsWith("?") -> "I'll check and let you know soon."
            item.text.contains("when", true) || item.text.contains("time", true) -> "Sounds good, I'll see you then."
            item.text.contains("thanks", true) || item.text.contains("thank you", true) -> "You're welcome!"
            else -> "Sounds good!"
        }

        val recipient = item.title.ifBlank { "the sender" }
        return ActionResult.success(
            spoken = "Drafted reply for $recipient on ${item.appName}: \"$draft\". Would you like me to send it?",
            data = mapOf(
                "notification_key" to item.key,
                "app" to item.appName,
                "sender" to recipient,
                "draft" to draft,
                "can_reply" to item.canReply
            )
        )
    }

    private fun executeReplyNotification(action: AndroidAction.ReplyToNotification): ActionResult {
        if (!checkNotificationAccess()) {
            return ActionResult.failure(
                spoken = "Notification access is required to send notification replies.",
                error = "notification_access_disabled"
            )
        }

        val targetItem = ZayaNotificationListener.findNotificationForReply(
            context = context,
            targetKey = action.notificationKey,
            targetSender = action.targetSender,
            targetPackage = action.targetPackage
        )

        if (targetItem == null) {
            val targetDesc = action.targetSender ?: action.targetPackage ?: "that app"
            return ActionResult.failure(
                spoken = "I couldn't find an active notification from $targetDesc to reply to.",
                error = "notification_not_found"
            )
        }

        val replyText = action.text.trim()
        if (replyText.isBlank()) {
            return ActionResult.failure("Notification reply text cannot be blank.", error = "malformed_parameters")
        }
        if (replyText.length > 2000) {
            return ActionResult.failure("Notification reply text exceeds maximum allowed length.", error = "malformed_parameters")
        }

        if (!action.confirmed) {
            val recipient = targetItem.title.ifBlank { "the sender" }
            return ActionResult.needsConfirmation(
                spoken = "Do you want me to reply to $recipient on ${targetItem.appName}: \"$replyText\"?",
                actionId = "reply_notification",
                payload = mapOf(
                    "notification_key" to targetItem.key,
                    "sender" to recipient,
                    "app" to targetItem.appName,
                    "text" to replyText
                )
            )
        }

        // Deduplication safety check for confirmed notification replies
        val replySignature = "reply_notification:${targetItem.key}:${replyText.hashCode()}"
        if (deduplicator.isDuplicate(replySignature)) {
            return ActionResult.failure(
                spoken = "Prevented duplicate reply to ${targetItem.appName} within the safety window.",
                error = "duplicate_consequential_action_prevented",
                data = mapOf("app" to targetItem.appName)
            )
        }
        deduplicator.record(replySignature)

        return when (val outcome = ZayaNotificationListener.sendReply(targetItem.key, replyText)) {
            is ReplyOutcome.Success -> {
                ActionResult.success(
                    spoken = "Reply dispatched to ${targetItem.appName} for ${targetItem.title.ifBlank { "recipient" }}.",
                    data = mapOf("app" to targetItem.appName, "recipient" to targetItem.title)
                )
            }
            is ReplyOutcome.NoRemoteInput -> {
                if (outcome.contentIntent != null) {
                    try {
                        outcome.contentIntent.send()
                        ActionResult.success(
                            spoken = "${targetItem.appName} doesn't support direct voice replies. I've opened the app for you.",
                            data = mapOf("app" to targetItem.appName, "opened_app" to true)
                        )
                    } catch (e: Exception) {
                        ActionResult.failure("Could not open ${targetItem.appName}: ${e.message}", error = "intent_failed")
                    }
                } else {
                    ActionResult.failure("${targetItem.appName} notification does not support inline replies.", error = "no_remote_input")
                }
            }
            is ReplyOutcome.NotificationNotFound -> {
                ActionResult.failure("Notification was dismissed or is no longer active.", error = "stale_notification")
            }
            is ReplyOutcome.Failed -> {
                ActionResult.failure("Could not dispatch reply: ${outcome.reason}", error = "reply_failed")
            }
        }
    }

    private suspend fun executeCaptureScreen(): ActionResult {
        if (!ScreenCaptureManager.hasConsent()) {
            screenCaptureManager.requestConsent()
            return ActionResult.permissionRequired(
                permission = "android.permission.MEDIA_PROJECTION",
                spoken = "Screen capture authorization is required. Please grant the screen recording dialog to proceed."
            )
        }

        return when (val frame = screenCaptureManager.captureScreenFrame()) {
            is ScreenFrameResult.Success -> {
                ActionResult.success(
                    spoken = "Screen captured at ${frame.width}x${frame.height}.",
                    data = mapOf(
                        "width" to frame.width,
                        "height" to frame.height,
                        "timestamp" to frame.timestamp,
                        "captured" to true
                    )
                )
            }
            is ScreenFrameResult.ConsentRequired -> {
                ActionResult.permissionRequired(
                    permission = "android.permission.MEDIA_PROJECTION",
                    spoken = "Screen capture authorization is required."
                )
            }
            is ScreenFrameResult.Timeout -> {
                ActionResult.failure("Screen capture timed out waiting for display frame.", error = "TimeoutException")
            }
            is ScreenFrameResult.Failed -> {
                ActionResult.failure("Screen capture failed: ${frame.reason}", error = "CaptureError")
            }
        }
    }

    private suspend fun executeDescribeScreen(action: AndroidAction.DescribeScreen): ActionResult {
        if (!ScreenCaptureManager.hasConsent()) {
            screenCaptureManager.requestConsent()
            return ActionResult.permissionRequired(
                permission = "android.permission.MEDIA_PROJECTION",
                spoken = "Screen capture authorization is required to describe what is on screen."
            )
        }

        val analysis = screenCaptureManager.analyzeScreen(action.prompt)
        return if (analysis.summary.contains("consent is required", ignoreCase = true)) {
            ActionResult.permissionRequired(
                permission = "android.permission.MEDIA_PROJECTION",
                spoken = analysis.summary
            )
        } else if (analysis.extractedLines.isEmpty() && analysis.resolution == "0x0") {
            ActionResult.failure(analysis.summary, error = "ScreenAnalysisError")
        } else {
            ActionResult.success(
                spoken = analysis.summary,
                data = mapOf(
                    "resolution" to analysis.resolution,
                    "features" to analysis.extractedLines,
                    "prompt" to (action.prompt ?: "describe"),
                    "timestamp" to analysis.timestamp
                )
            )
        }
    }

    private suspend fun executeExtractVisibleText(action: AndroidAction.ExtractVisibleText): ActionResult {
        if (!ScreenCaptureManager.hasConsent()) {
            screenCaptureManager.requestConsent()
            return ActionResult.permissionRequired(
                permission = "android.permission.MEDIA_PROJECTION",
                spoken = "Screen capture authorization is required to extract visible text."
            )
        }

        val analysis = screenCaptureManager.analyzeScreen(
            action.filter?.let { "Extract text matching: $it" } ?: "Extract visible text"
        )
        return if (analysis.summary.contains("consent is required", ignoreCase = true)) {
            ActionResult.permissionRequired(
                permission = "android.permission.MEDIA_PROJECTION",
                spoken = analysis.summary
            )
        } else if (analysis.extractedLines.isEmpty() && analysis.resolution == "0x0") {
            ActionResult.failure(analysis.summary, error = "ScreenAnalysisError")
        } else {
            val text = if (analysis.extractedLines.isNotEmpty()) {
                analysis.extractedLines.joinToString("\n")
            } else {
                "No readable text detected on screen."
            }
            ActionResult.success(
                spoken = "Visible text extracted from screen.",
                data = mapOf(
                    "text" to text,
                    "lines" to analysis.extractedLines,
                    "resolution" to analysis.resolution
                )
            )
        }
    }

    private suspend fun executeSummarizeScreen(action: AndroidAction.SummarizeScreen): ActionResult {
        if (!ScreenCaptureManager.hasConsent()) {
            screenCaptureManager.requestConsent()
            return ActionResult.permissionRequired(
                permission = "android.permission.MEDIA_PROJECTION",
                spoken = "Screen capture authorization is required to summarize the screen."
            )
        }

        val analysis = screenCaptureManager.analyzeScreen(
            action.focus?.let { "Summarize screen with focus on: $it" } ?: "Summarize visible screen"
        )
        return if (analysis.summary.contains("consent is required", ignoreCase = true)) {
            ActionResult.permissionRequired(
                permission = "android.permission.MEDIA_PROJECTION",
                spoken = analysis.summary
            )
        } else if (analysis.extractedLines.isEmpty() && analysis.resolution == "0x0") {
            ActionResult.failure(analysis.summary, error = "ScreenAnalysisError")
        } else {
            ActionResult.success(
                spoken = analysis.summary,
                data = mapOf(
                    "resolution" to analysis.resolution,
                    "focus" to (action.focus ?: "all"),
                    "timestamp" to analysis.timestamp
                )
            )
        }
    }

    private suspend fun executeScrollScreen(action: AndroidAction.ScrollScreen): ActionResult {
        val interactionService = ZayaInteractionService.getInstance()
        if (interactionService == null || !ZayaInteractionService.isServiceEnabled()) {
            return ActionResult.permissionRequired(
                permission = "android.settings.ACCESSIBILITY_SETTINGS",
                spoken = "Accessibility Service authorization is required to scroll the screen."
            )
        }
        return when (val outcome = interactionService.scroll(action.direction, action.count, action.distance)) {
            is ScrollOutcome.Success -> {
                ActionResult.success(
                    spoken = "Scrolled ${outcome.direction} ${outcome.count} time(s).",
                    data = mapOf("direction" to outcome.direction, "count" to outcome.count)
                )
            }
            is ScrollOutcome.Cancelled -> {
                ActionResult.cancelled("Scroll was cancelled after ${outcome.completedCount} actions.")
            }
            is ScrollOutcome.Failed -> {
                ActionResult.failure(outcome.reason, error = "scroll_failed")
            }
        }
    }

    private suspend fun executeTapScreen(action: AndroidAction.TapScreen): ActionResult {
        val interactionService = ZayaInteractionService.getInstance()
        if (interactionService == null || !ZayaInteractionService.isServiceEnabled()) {
            return ActionResult.permissionRequired(
                permission = "android.settings.ACCESSIBILITY_SETTINGS",
                spoken = "Accessibility Service authorization is required to interact with on-screen controls."
            )
        }
        if (action.label != null) {
            return when (val outcome = interactionService.tapByLabel(action.label, action.confirmed)) {
                is TapOutcome.Success -> {
                    ActionResult.success(
                        spoken = "Tapped '${outcome.target}'.",
                        data = mapOf("target" to outcome.target)
                    )
                }
                is TapOutcome.RequiresConfirmation -> {
                    ActionResult.needsConfirmation(
                        spoken = "Please confirm tapping '${outcome.label}': ${outcome.reason}",
                        actionId = "tap_screen",
                        payload = mapOf("label" to outcome.label, "reason" to outcome.reason)
                    )
                }
                is TapOutcome.SecurityRestricted -> {
                    ActionResult.failure("Security restriction: ${outcome.reason}", error = "security_restricted")
                }
                is TapOutcome.NotFound -> {
                    ActionResult.failure("Could not locate '${outcome.label}' on the visible screen.", error = "not_found")
                }
                is TapOutcome.Ambiguous -> {
                    ActionResult.failure("Found multiple (${outcome.count}) controls matching '${outcome.label}'. Please be more specific.", error = "ambiguous")
                }
                is TapOutcome.Failed -> {
                    ActionResult.failure("Tap failed: ${outcome.reason}", error = "tap_failed")
                }
            }
        } else if (action.x != null && action.y != null) {
            val ok = interactionService.tapCoordinates(action.x, action.y)
            return if (ok) {
                ActionResult.success("Tapped coordinates (${action.x}, ${action.y}).", data = mapOf("x" to action.x, "y" to action.y))
            } else {
                ActionResult.failure("Failed to tap coordinates (${action.x}, ${action.y}). Out of bounds or gesture failed.", error = "gesture_failed")
            }
        } else {
            return ActionResult.failure("TapScreen requires either a target label or (x, y) coordinates.", error = "invalid_arguments")
        }
    }

    private fun executeNavigateBack(): ActionResult {
        val interactionService = ZayaInteractionService.getInstance()
        if (interactionService != null && interactionService.navigateBack()) {
            return ActionResult.success("Navigated back.")
        }
        return ActionResult.permissionRequired("android.settings.ACCESSIBILITY_SETTINGS", "Back navigation requires Accessibility Service authorization.")
    }

    private fun executeNavigateHome(): ActionResult {
        val interactionService = ZayaInteractionService.getInstance()
        if (interactionService != null && interactionService.navigateHome()) {
            return ActionResult.success("Navigated to home screen.")
        }
        return ActionResult.permissionRequired("android.settings.ACCESSIBILITY_SETTINGS", "Home navigation requires Accessibility Service authorization.")
    }

    private fun executeCloseOverlay(): ActionResult {
        val interactionService = ZayaInteractionService.getInstance()
        if (interactionService != null && interactionService.navigateBack()) {
            return ActionResult.success("Closed visible overlay.")
        }
        return ActionResult.permissionRequired("android.settings.ACCESSIBILITY_SETTINGS", "Closing overlay requires Accessibility Service authorization.")
    }

    private suspend fun executeNavigateReel(action: AndroidAction.NavigateReel): ActionResult {
        val interactionService = ZayaInteractionService.getInstance()
        if (interactionService == null || !ZayaInteractionService.isServiceEnabled()) {
            return ActionResult.permissionRequired("android.settings.ACCESSIBILITY_SETTINGS", "Reel navigation requires Accessibility Service authorization.")
        }
        return when (val outcome = interactionService.navigateReel(action.action, action.count)) {
            is ScrollOutcome.Success -> {
                ActionResult.success("Navigated ${action.action} reel.", data = mapOf("action" to action.action, "count" to outcome.count))
            }
            is ScrollOutcome.Cancelled -> {
                ActionResult.cancelled("Reel navigation cancelled.")
            }
            is ScrollOutcome.Failed -> {
                ActionResult.failure("Reel navigation failed: ${outcome.reason}", error = "navigation_failed")
            }
        }
    }

    // ── Multi-Step Tasks & Cancellation ─────────────────────────────────────

    private suspend fun executeRunTask(action: AndroidAction.RunTask): ActionResult {
        if (action.actions.isEmpty()) {
            return ActionResult.failure("No actions provided for task execution.", error = "empty_task")
        }

        val steps = action.actions.mapIndexed { index, act ->
            TaskStep(
                stepIndex = index + 1,
                actionId = act.actionId,
                description = "Step ${index + 1}: ${act.actionId}",
                action = act
            )
        }

        val taskId = action.taskId.ifBlank { java.util.UUID.randomUUID().toString() }
        val report = taskCoordinator.executeTask(
            taskId = taskId,
            originalGoal = "Run task $taskId",
            steps = steps
        )

        return when (report.status) {
            TaskOverallStatus.COMPLETED -> ActionResult.success(
                spoken = report.summary,
                data = report.data + mapOf("task_id" to report.taskId, "completed" to true)
            )
            TaskOverallStatus.PARTIALLY_COMPLETED -> ActionResult.failure(
                spoken = report.summary,
                error = "partially_completed",
                data = report.data + mapOf(
                    "task_id" to report.taskId,
                    "completed_steps" to report.completedSteps,
                    "total_steps" to report.totalSteps
                )
            )
            TaskOverallStatus.CANCELLED -> ActionResult.cancelled(report.summary)
            TaskOverallStatus.NEEDS_CONFIRMATION -> ActionResult.needsConfirmation(
                spoken = report.summary,
                actionId = "run_task",
                payload = report.data
            )
            else -> ActionResult.failure(spoken = report.summary, error = "task_failed", data = report.data)
        }
    }

    private fun executeCancelTask(action: AndroidAction.CancelTask): ActionResult {
        val targetId = action.taskId.ifBlank {
            taskCoordinator.activeTask.value?.taskId ?: ""
        }

        if (targetId.isBlank()) {
            return ActionResult.failure("No active task running to cancel.", error = "no_active_task")
        }

        val cancelled = taskCoordinator.cancelTask(targetId, "Cancelled by user")
        return if (cancelled) {
            val state = taskCoordinator.activeTask.value
            val irreversibleNote = if (!state?.irreversibleActionsCompleted.isNullOrEmpty()) {
                " Note: ${state!!.irreversibleActionsCompleted.joinToString("; ")} was already executed and cannot be recalled."
            } else ""

            ActionResult.cancelled("Task $targetId cancelled.$irreversibleNote")
        } else {
            ActionResult.failure("Task $targetId was not active or could not be cancelled.", error = "cancel_failed")
        }
    }

    private suspend fun executePlanAndExecuteTask(action: AndroidAction.PlanAndExecuteTask): ActionResult {
        val (steps, clarification) = TaskPlanner.planFromRequest(action.prompt, registry)
        if (clarification != null) {
            return ActionResult.failure(spoken = clarification, error = "clarification_needed", data = mapOf("prompt" to action.prompt))
        }

        if (steps.isEmpty()) {
            return ActionResult.failure(
                spoken = "Unable to create a multi-step plan for '${action.prompt}'.",
                error = "unsupported_plan"
            )
        }

        val taskId = action.taskId.ifBlank { java.util.UUID.randomUUID().toString() }
        val report = taskCoordinator.executeTask(
            taskId = taskId,
            originalGoal = action.prompt,
            steps = steps
        )

        return when (report.status) {
            TaskOverallStatus.COMPLETED -> ActionResult.success(
                spoken = report.summary,
                data = report.data + mapOf("task_id" to report.taskId, "completed" to true)
            )
            TaskOverallStatus.PARTIALLY_COMPLETED -> ActionResult.failure(
                spoken = report.summary,
                error = "partially_completed",
                data = report.data + mapOf(
                    "task_id" to report.taskId,
                    "completed_steps" to report.completedSteps,
                    "total_steps" to report.totalSteps
                )
            )
            TaskOverallStatus.CANCELLED -> ActionResult.cancelled(report.summary)
            TaskOverallStatus.NEEDS_CONFIRMATION -> ActionResult.needsConfirmation(
                spoken = report.summary,
                actionId = "plan_and_execute_task",
                payload = report.data
            )
            TaskOverallStatus.CLARIFICATION_REQUIRED -> ActionResult.failure(
                spoken = report.clarificationQuestion ?: report.summary,
                error = "clarification_needed"
            )
            else -> ActionResult.failure(spoken = report.summary, error = "task_failed", data = report.data)
        }
    }

    // ── Personal Memory Handlers ────────────────────────────────────────────

    private fun executeRememberMemory(action: AndroidAction.RememberMemory): ActionResult {
        val cat = com.zaya.companion.memory.MemoryCategory.fromString(action.category)
        return when (val res = memoryStore.saveMemory(action.key, action.value, cat, action.confirmed)) {
            is com.zaya.companion.memory.MemorySaveResult.Saved -> {
                ActionResult.success(
                    spoken = res.message,
                    data = mapOf(
                        "id" to res.memory.id,
                        "key" to res.memory.key,
                        "value" to res.memory.value,
                        "category" to res.memory.category.name
                    )
                )
            }
            is com.zaya.companion.memory.MemorySaveResult.RequiresConfirmation -> {
                ActionResult.needsConfirmation(
                    spoken = res.prompt,
                    actionId = "remember_memory",
                    payload = mapOf(
                        "key" to res.key,
                        "value" to res.value,
                        "category" to res.category.name
                    )
                )
            }
            is com.zaya.companion.memory.MemorySaveResult.SensitiveDataBlocked -> {
                ActionResult.failure(
                    spoken = "For your privacy and security, I cannot store sensitive details such as passwords, authentication tokens, or payment credentials.",
                    error = "sensitive_data_blocked"
                )
            }
            is com.zaya.companion.memory.MemorySaveResult.Invalid -> {
                ActionResult.failure(res.reason, error = "invalid_argument")
            }
        }
    }

    private fun executeForgetMemory(action: AndroidAction.ForgetMemory): ActionResult {
        val cat = action.category?.let { com.zaya.companion.memory.MemoryCategory.fromString(it) }
        val forgotten = memoryStore.forgetMemory(action.key, cat)
        return if (forgotten) {
            ActionResult.success(
                spoken = "I have forgotten '${action.key}' and removed it from your saved preferences.",
                data = mapOf("key" to action.key, "forgotten" to true)
            )
        } else {
            ActionResult.failure(
                spoken = "I don't have anything saved about '${action.key}'.",
                error = "memory_not_found"
            )
        }
    }

    private fun executeQueryMemory(action: AndroidAction.QueryMemory): ActionResult {
        val matches = memoryStore.getRelevantMemories(action.query)
        return if (matches.isEmpty()) {
            ActionResult.success(
                spoken = "I don't have any saved preferences matching '${action.query}'.",
                data = mapOf("count" to 0, "results" to emptyList<Any>())
            )
        } else {
            val descriptions = matches.map { "${it.category.displayName} - ${it.key}: ${it.value}" }
            val spoken = "Found ${matches.size} saved preference${if (matches.size > 1) "s" else ""}: ${descriptions.joinToString("; ")}."
            ActionResult.success(
                spoken = spoken,
                data = mapOf(
                    "count" to matches.size,
                    "memories" to matches.map {
                        mapOf("key" to it.key, "value" to it.value, "category" to it.category.name)
                    }
                )
            )
        }
    }

    // ── Expanded PC & OpenJarvis Handlers ───────────────────────────────────

    private fun executeEvaluateMath(action: AndroidAction.EvaluateMath): ActionResult {
        val res = systemUtils.evaluateMath(action.expression)
        return if (res.success && res.result != null) {
            ActionResult.success(
                spoken = "The answer is ${res.formatted}.",
                data = mapOf(
                    "expression" to action.expression,
                    "result" to res.result,
                    "formatted" to res.formatted
                )
            )
        } else {
            ActionResult.failure(
                spoken = res.formatted,
                error = res.error ?: "math_evaluation_error"
            )
        }
    }

    private fun executeGetDeviceDiagnostics(): ActionResult {
        val diag = systemUtils.getDeviceDiagnostics()
        val battery = diag["battery_level"] as? Int ?: 0
        val isCharging = diag["is_charging"] as? Boolean ?: false
        val chargeStr = if (isCharging) " and charging" else ""
        val availStorage = diag["storage_available_gb"]
        val ramUsed = diag["ram_used_percent"]
        val net = diag["network_type"]
        val spoken = "Battery is at $battery percent$chargeStr. Network is $net. Storage has $availStorage GB free, with $ramUsed percent RAM in use."
        return ActionResult.success(spoken, diag)
    }

    private fun executeWebSearch(action: AndroidAction.WebSearch): ActionResult {
        val res = systemUtils.searchWeb(action.query, action.openInBrowser)
        return ActionResult.success(
            spoken = res.summary,
            data = mapOf(
                "query" to res.query,
                "url" to res.searchUrl,
                "opened_in_browser" to res.openedInBrowser
            )
        )
    }

    private fun executeGetWeather(action: AndroidAction.GetWeather): ActionResult {
        val weather = systemUtils.getWeather(action.location)
        return ActionResult.success(
            spoken = weather.summary,
            data = mapOf(
                "location" to weather.location,
                "temperature_c" to weather.temperatureC,
                "condition" to weather.condition,
                "humidity" to weather.humidity,
                "wind_kmh" to weather.windKmh,
                "is_live" to weather.isLive
            )
        )
    }

    private fun executeGetDailyBriefing(): ActionResult {
        val activeCount = taskCoordinator.activeTask.value?.let { 1 } ?: 0
        val unreadNotifs = com.zaya.companion.service.ZayaNotificationListener.getActiveNotifications(context).size
        val briefing = systemUtils.getDailyBriefing(activeCount, unreadNotifs)
        val speech = briefing["spoken_briefing"] as? String ?: "Briefing compiled successfully."
        return ActionResult.success(speech, briefing)
    }

    private fun executeSetTimer(action: AndroidAction.SetTimer): ActionResult {
        if (action.seconds <= 0) {
            return ActionResult.failure("Timer duration must be greater than zero.", error = "invalid_timer_duration")
        }
        val ok = systemUtils.setTimer(action.seconds, action.label)
        return if (ok) {
            ActionResult.success(
                spoken = "Timer set for ${action.seconds} seconds.",
                data = mapOf("seconds" to action.seconds, "label" to action.label)
            )
        } else {
            ActionResult.failure("Could not start timer.", error = "timer_failed")
        }
    }

    private fun executeSetAlarm(action: AndroidAction.SetAlarm): ActionResult {
        if (action.hour !in 0..23 || action.minutes !in 0..59) {
            return ActionResult.failure("Invalid alarm time. Hour must be 0-23 and minutes 0-59.", error = "invalid_alarm_time")
        }
        val ok = systemUtils.setAlarm(action.hour, action.minutes, action.label, action.skipUi)
        val timeFormatted = String.format(java.util.Locale.US, "%02d:%02d", action.hour, action.minutes)
        return if (ok) {
            ActionResult.success(
                spoken = "Alarm set for $timeFormatted.",
                data = mapOf("hour" to action.hour, "minutes" to action.minutes, "label" to action.label)
            )
        } else {
            ActionResult.failure("Could not set alarm.", error = "alarm_failed")
        }
    }

    private fun executeGetClipboard(): ActionResult {
        val text = systemUtils.getClipboardText()
        return if (text.isNullOrBlank()) {
            ActionResult.success("The clipboard is currently empty.", mapOf("empty" to true))
        } else {
            val preview = if (text.length > 80) text.take(77) + "..." else text
            ActionResult.success(
                spoken = "Clipboard contains: '$preview'.",
                data = mapOf("text" to text, "empty" to false, "length" to text.length)
            )
        }
    }

    private fun executeSetClipboard(action: AndroidAction.SetClipboard): ActionResult {
        val ok = systemUtils.setClipboardText(action.text)
        return if (ok) {
            ActionResult.success(
                spoken = "Copied text to clipboard.",
                data = mapOf("length" to action.text.length)
            )
        } else {
            ActionResult.failure("Could not copy to clipboard.", error = "clipboard_failed")
        }
    }

    private fun executeSendWhatsAppMessage(action: AndroidAction.SendWhatsAppMessage): ActionResult {
        if (!action.confirmed) {
            return ActionResult.needsConfirmation(
                spoken = "Would you like me to open WhatsApp and send '${action.message}' to ${action.recipient}?",
                actionId = "send_whatsapp_message",
                payload = mapOf(
                    "recipient" to action.recipient,
                    "message" to action.message
                )
            )
        }

        val sig = "whatsapp:${action.recipient}:${action.message}"
        if (deduplicator.isDuplicate(sig)) {
            return ActionResult.failure(
                spoken = "A WhatsApp message to ${action.recipient} was already recently dispatched.",
                error = "duplicate_dispatched"
            )
        }
        deduplicator.record(sig)

        val ok = systemUtils.sendWhatsAppMessage(action.recipient, action.message)
        return if (ok) {
            ActionResult.success(
                spoken = "Opened WhatsApp to send message to ${action.recipient}.",
                data = mapOf("recipient" to action.recipient, "message" to action.message)
            )
        } else {
            ActionResult.failure("Could not launch WhatsApp.", error = "whatsapp_failed")
        }
    }

    private fun executeInspectStorage(action: AndroidAction.InspectStorage): ActionResult {
        val info = systemUtils.inspectStorage(action.path)
        val freeMb = info["free_storage_mb"]
        val fileCount = info["file_count"]
        val dir = info["directory_inspected"]
        val spoken = "Inspected storage at $dir. Free space: $freeMb MB. Found $fileCount files."
        return ActionResult.success(spoken, info)
    }

    private fun executeSetVolume(action: AndroidAction.SetVolume): ActionResult {
        val ok = systemUtils.setVolume(action.level, action.streamType)
        return if (ok) {
            ActionResult.success(
                spoken = "Set ${action.streamType} volume to ${action.level.coerceIn(0, 100)} percent.",
                data = mapOf("level" to action.level, "stream_type" to action.streamType)
            )
        } else {
            ActionResult.failure("Could not adjust volume.", error = "volume_failed")
        }
    }

    private fun executeSetRingerMode(action: AndroidAction.SetRingerMode): ActionResult {
        val ok = systemUtils.setRingerMode(action.mode)
        return if (ok) {
            ActionResult.success(
                spoken = "Phone ringer mode set to ${action.mode}.",
                data = mapOf("mode" to action.mode)
            )
        } else {
            ActionResult.failure("Could not change ringer mode.", error = "ringer_mode_failed")
        }
    }

    private fun executeExecutePcCommand(action: AndroidAction.ExecutePcCommand): ActionResult {
        val resource = action.parameters["path"] as? String
            ?: action.parameters["process_name"] as? String
            ?: action.parameters["app_id"] as? String
            ?: "PC resource"
        val isConsequential = action.command in listOf("write_file", "terminate_process", "delete_file", "install_software")
        val sideEffects = when (action.command) {
            "write_file" -> "Modifying or overwriting file at '$resource'"
            "terminate_process" -> "Terminating running process '$resource'"
            else -> "Executing remote command '${action.command}' on paired PC"
        }
        val isReversible = false

        if (!action.confirmed && isConsequential) {
            return ActionResult.needsConfirmation(
                spoken = "Confirmation required: Do you approve executing '${action.command}' on $resource? Potential side effect: $sideEffects.",
                actionId = "execute_pc_command",
                payload = mapOf(
                    "target_pc" to "Paired PC",
                    "action" to action.command,
                    "resource" to resource,
                    "parameters" to action.parameters,
                    "potential_side_effects" to sideEffects,
                    "reversible" to isReversible
                )
            )
        }
        return ActionResult.success(
            spoken = "Dispatched remote PC command '${action.command}'.",
            data = mapOf(
                "command" to action.command,
                "parameters" to action.parameters,
                "resource" to resource,
                "relayed" to true
            )
        )
    }

    private fun executeConvertCurrency(action: AndroidAction.ConvertCurrency): ActionResult {
        val res = systemUtils.convertCurrency(action.amount, action.from, action.to)
        return if (res["success"] == true) {
            ActionResult.success(
                spoken = res["formatted"] as String,
                data = res
            )
        } else {
            ActionResult.failure(
                spoken = res["error"] as String,
                error = "currency_conversion_failed"
            )
        }
    }

    private fun executeReadFile(action: AndroidAction.ReadFile): ActionResult {
        val res = systemUtils.readFile(action.path, action.maxLines)
        return if (res["success"] == true) {
            val lines = res["line_count"]
            val name = res["file_name"]
            ActionResult.success(
                spoken = "Read $lines lines from $name.",
                data = res
            )
        } else {
            ActionResult.failure(
                spoken = res["error"] as String,
                error = "file_read_failed"
            )
        }
    }

    private fun executeWriteFile(action: AndroidAction.WriteFile): ActionResult {
        if (!action.confirmed) {
            return ActionResult.needsConfirmation(
                spoken = "Are you sure you want to write to file '${action.path}'?",
                actionId = "write_file",
                payload = mapOf(
                    "path" to action.path,
                    "content" to action.content,
                    "append" to action.append
                )
            )
        }
        val res = systemUtils.writeFile(action.path, action.content, action.append)
        return if (res["success"] == true) {
            val name = res["file_name"]
            ActionResult.success(
                spoken = "Successfully wrote to $name.",
                data = res
            )
        } else {
            ActionResult.failure(
                spoken = res["error"] as String,
                error = "file_write_failed"
            )
        }
    }

    private fun executeThink(action: AndroidAction.Think): ActionResult {
        val res = systemUtils.think(action.thought)
        return ActionResult.success(
            spoken = "Plan recorded.",
            data = res + ("silent" to true)
        )
    }

    private fun executeLookupKnowledge(action: AndroidAction.LookupKnowledge): ActionResult {
        val res = systemUtils.lookupKnowledge(action.topic)
        return ActionResult.success(
            spoken = "Retrieved knowledge for '${action.topic}'.",
            data = res
        )
    }
}
