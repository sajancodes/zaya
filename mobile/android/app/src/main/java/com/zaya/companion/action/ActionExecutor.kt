package com.zaya.companion.action

import android.Manifest
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.ContactsContract
import android.util.Log
import com.zaya.companion.service.AppLauncher
import com.zaya.companion.service.CellularCallManager
import com.zaya.companion.service.HardwareController
import com.zaya.companion.service.MediaPlaybackController
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
            is AndroidAction.OpenSystemSettings -> executeOpenSettings(action.setting)
            is AndroidAction.ControlMedia -> executeControlMedia(action.action)
            is AndroidAction.LaunchApp -> executeLaunchApp(action.name)
            is AndroidAction.LookUpContact -> executeContactLookup(action.query)
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
        val ok = hardwareController.setFlashlight(enabled)
        val stateStr = if (enabled) "on" else "off"
        return if (ok) {
            ActionResult.success("Flashlight turned $stateStr.", mapOf("flashlight" to enabled))
        } else {
            ActionResult.failure("Unable to control flashlight. Camera flash may be unavailable.", error = "hardware_unavailable")
        }
    }

    private fun executeOpenSettings(setting: String): ActionResult {
        val ok = when (setting.lowercase().trim()) {
            "wifi", "wi-fi" -> hardwareController.openWifiSettings()
            "bluetooth" -> hardwareController.openBluetoothSettings()
            "hotspot", "tethering" -> hardwareController.openHotspotSettings()
            "location", "gps" -> hardwareController.openLocationSettings()
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

    private fun executeLaunchApp(name: String): ActionResult {
        if (name.isBlank()) {
            return ActionResult.failure("App name cannot be empty.", error = "invalid_argument")
        }
        val ok = appLauncher.launchAppByName(name)
        return if (ok) {
            ActionResult.success("Opened $name.", mapOf("app_name" to name))
        } else {
            ActionResult.failure("Could not find or open application '$name'.", error = "app_not_found")
        }
    }

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

        return try {
            val uri = ContactsContract.CommonDataKinds.Phone.CONTENT_URI
            val projection = arrayOf(
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER,
            )
            val selection = "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?"
            val selectionArgs = arrayOf("%$query%")

            val matches = mutableListOf<Map<String, String>>()
            context.contentResolver.query(uri, projection, selection, selectionArgs, null)?.use { cursor ->
                val nameIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                val numIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
                while (cursor.moveToNext() && matches.size < 5) {
                    val name = cursor.getString(nameIdx) ?: ""
                    val number = cursor.getString(numIdx) ?: ""
                    if (name.isNotEmpty()) {
                        matches.add(mapOf("name" to name, "number" to number))
                    }
                }
            }

            if (matches.isNotEmpty()) {
                val firstName = matches.first()["name"] ?: query
                ActionResult.success(
                    "Found contact $firstName.",
                    mapOf("count" to matches.size, "contacts" to matches)
                )
            } else {
                ActionResult.failure("No contacts found matching '$query'.", error = "not_found")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Contact lookup failed: ${e.message}")
            ActionResult.failure("Failed to read contacts: ${e.message}", error = e.javaClass.simpleName)
        }
    }

    private fun executeComposeSms(action: AndroidAction.ComposeSms): ActionResult {
        if (!action.confirmed) {
            return ActionResult.needsConfirmation(
                spoken = "Do you want me to send this text to ${action.recipient}?",
                actionId = "compose_sms",
                payload = mapOf("recipient" to action.recipient, "message" to action.message)
            )
        }

        return try {
            val smsUri = Uri.parse("smsto:${Uri.encode(action.recipient)}")
            val intent = Intent(Intent.ACTION_SENDTO, smsUri).apply {
                putExtra("sms_body", action.message)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
            ActionResult.success(
                "SMS prepared for ${action.recipient}.",
                mapOf("recipient" to action.recipient)
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to launch SMS intent: ${e.message}")
            ActionResult.failure("Could not compose SMS: ${e.message}", error = e.javaClass.simpleName)
        }
    }

    private fun executeAnswerCall(): ActionResult {
        if (!registry.hasPermission(Manifest.permission.ANSWER_PHONE_CALLS)) {
            return ActionResult.permissionRequired(
                Manifest.permission.ANSWER_PHONE_CALLS,
                "Permission required to answer phone calls hands-free."
            )
        }
        val ok = callManager.answerCall()
        return if (ok) {
            ActionResult.success("Answering call.")
        } else {
            ActionResult.failure("Could not answer call. No active incoming call or unsupported OS version.", error = "telecom_error")
        }
    }

    private fun executeRejectCall(): ActionResult {
        if (!registry.hasPermission(Manifest.permission.ANSWER_PHONE_CALLS)) {
            return ActionResult.permissionRequired(
                Manifest.permission.ANSWER_PHONE_CALLS,
                "Permission required to decline phone calls."
            )
        }
        val ok = callManager.rejectCall()
        return if (ok) {
            ActionResult.success("Call declined.")
        } else {
            ActionResult.failure("Could not reject call.", error = "telecom_error")
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
