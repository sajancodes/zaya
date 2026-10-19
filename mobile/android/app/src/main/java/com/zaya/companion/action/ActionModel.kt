package com.zaya.companion.action

import org.json.JSONObject

/**
 * Risk classification for phone control actions.
 */
enum class ActionRisk {
    LOW,        // Read-only or reversible hardware toggles (e.g. flashlight, volume, battery status)
    MEDIUM,     // Navigation and media playback (e.g. open app, play/pause music)
    HIGH,       // Communication handling and active state changes (e.g. answer call, screen vision)
    CRITICAL,   // Consequential communications (e.g. dispatch SMS, place outgoing call)
}

/**
 * Execution outcome status for phone control actions.
 */
enum class ActionResultStatus {
    SUCCESS,
    FAILURE,
    PERMISSION_REQUIRED,
    NEEDS_CONFIRMATION,
    UNSUPPORTED,
    CANCELLED,
}

/**
 * Structured outcome returned by the ActionExecutor.
 */
data class ActionResult(
    val status: ActionResultStatus,
    val spokenMessage: String,
    val data: Map<String, Any?> = emptyMap(),
    val error: String? = null,
) {
    fun toJsonObject(): JSONObject = JSONObject().apply {
        put("status", status.name)
        put("spoken_message", spokenMessage)
        put("data", JSONObject(data))
        if (error != null) put("error", error)
    }

    companion object {
        fun success(spoken: String, data: Map<String, Any?> = emptyMap()) =
            ActionResult(ActionResultStatus.SUCCESS, spoken, data)

        fun failure(spoken: String, error: String? = null, data: Map<String, Any?> = emptyMap()) =
            ActionResult(ActionResultStatus.FAILURE, spoken, data, error)

        fun permissionRequired(permission: String, spoken: String = "Permission required: $permission") =
            ActionResult(ActionResultStatus.PERMISSION_REQUIRED, spoken, mapOf("permission" to permission), permission)

        fun needsConfirmation(spoken: String, actionId: String, payload: Map<String, Any?> = emptyMap()) =
            ActionResult(ActionResultStatus.NEEDS_CONFIRMATION, spoken, payload + ("action_id" to actionId))

        fun unsupported(reason: String) =
            ActionResult(ActionResultStatus.UNSUPPORTED, reason, emptyMap(), reason)

        fun cancelled(reason: String = "Action was cancelled") =
            ActionResult(ActionResultStatus.CANCELLED, reason, emptyMap(), reason)
    }
}

/**
 * Typed Android action model representing supported IRIS capabilities.
 */
sealed class AndroidAction(
    val actionId: String,
    val risk: ActionRisk,
    val requiresConfirmation: Boolean = false,
) {
    data class LaunchApp(val name: String) : AndroidAction("launch_app", ActionRisk.MEDIUM)

    data class SetFlashlight(val enabled: Boolean) : AndroidAction("set_flashlight", ActionRisk.LOW)

    data object GetFlashlightState : AndroidAction("get_flashlight_state", ActionRisk.LOW)

    data class OpenSystemSettings(
        val setting: String,
        val packageName: String? = null,
    ) : AndroidAction("open_settings", ActionRisk.LOW)

    data class ControlMedia(val action: String) : AndroidAction("control_media", ActionRisk.MEDIUM)

    data object GetMediaStatus : AndroidAction("get_media_status", ActionRisk.LOW)

    data class LookUpContact(val query: String) : AndroidAction("lookup_contact", ActionRisk.LOW)

    data class InitiateCall(
        val queryOrNumber: String,
        val directCall: Boolean = false,
        val confirmed: Boolean = false,
    ) : AndroidAction("initiate_call", ActionRisk.HIGH, requiresConfirmation = true)

    data object GetIncomingCallState : AndroidAction("get_incoming_call_state", ActionRisk.LOW)

    data class SetCallerAnnouncement(val enabled: Boolean) :
        AndroidAction("set_caller_announcement", ActionRisk.LOW)

    data class ComposeSms(
        val recipient: String,
        val message: String,
        val confirmed: Boolean = false,
        val directSend: Boolean = false,
    ) : AndroidAction("compose_sms", ActionRisk.CRITICAL, requiresConfirmation = true)

    data object AnswerCall : AndroidAction("answer_call", ActionRisk.HIGH)

    data object RejectCall : AndroidAction("reject_call", ActionRisk.HIGH)

    data class ReadNotifications(
        val packageFilter: String? = null,
        val limit: Int = 5,
    ) : AndroidAction("read_notifications", ActionRisk.LOW)

    data class ReadLatestNotification(
        val packageFilter: String? = null,
    ) : AndroidAction("read_latest_notification", ActionRisk.LOW)

    data class SummarizeNotifications(
        val packageFilter: String? = null,
    ) : AndroidAction("summarize_notifications", ActionRisk.LOW)

    data class DraftNotificationReply(
        val targetKey: String? = null,
        val targetSender: String? = null,
        val targetPackage: String? = null,
        val contextInstruction: String? = null,
    ) : AndroidAction("draft_notification_reply", ActionRisk.LOW)

    data class ReplyToNotification(
        val notificationKey: String? = null,
        val targetSender: String? = null,
        val targetPackage: String? = null,
        val text: String,
        val confirmed: Boolean = false,
    ) : AndroidAction("reply_notification", ActionRisk.HIGH, requiresConfirmation = true)

    data object CaptureScreen : AndroidAction("capture_screen", ActionRisk.HIGH)

    data class ScrollScreen(val direction: String) : AndroidAction("scroll_screen", ActionRisk.MEDIUM)

    data class TapScreen(val x: Float, val y: Float) : AndroidAction("tap_screen", ActionRisk.MEDIUM)

    data class RunTask(val taskId: String) : AndroidAction("run_task", ActionRisk.MEDIUM)

    data class CancelTask(val taskId: String) : AndroidAction("cancel_task", ActionRisk.LOW)
}
