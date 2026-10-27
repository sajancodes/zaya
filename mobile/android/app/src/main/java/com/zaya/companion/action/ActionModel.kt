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

    data class BrowseMedia(val kind: String, val query: String = "", val limit: Int = 10,
                           val uri: String = "") : AndroidAction("browse_media", ActionRisk.LOW)
    data class InitiateCall(
        val queryOrNumber: String,
        val directCall: Boolean = false,
        val confirmed: Boolean = false,
        val app: String = "phone",
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

    data object CaptureScreen : AndroidAction("capture_screen", ActionRisk.LOW)

    data class DescribeScreen(
        val prompt: String? = null,
    ) : AndroidAction("describe_screen", ActionRisk.LOW)

    data class ExtractVisibleText(
        val filter: String? = null,
    ) : AndroidAction("extract_visible_text", ActionRisk.LOW)

    data class SummarizeScreen(
        val focus: String? = null,
    ) : AndroidAction("summarize_screen", ActionRisk.LOW)

    data class ScrollScreen(
        val direction: String = "down",
        val count: Int = 1,
        val distance: String = "medium",
    ) : AndroidAction("scroll_screen", ActionRisk.MEDIUM)

    data class TapScreen(
        val x: Float? = null,
        val y: Float? = null,
        val label: String? = null,
        val confirmed: Boolean = false,
    ) : AndroidAction("tap_screen", ActionRisk.MEDIUM)

    data object NavigateBack : AndroidAction("navigate_back", ActionRisk.LOW)

    data object NavigateHome : AndroidAction("navigate_home", ActionRisk.LOW)

    data object CloseOverlay : AndroidAction("close_overlay", ActionRisk.LOW)

    data class NavigateReel(
        val action: String = "next",
        val count: Int = 1,
    ) : AndroidAction("navigate_reel", ActionRisk.MEDIUM)

    data class RunTask(
        val taskId: String,
        val actions: List<AndroidAction> = emptyList(),
    ) : AndroidAction("run_task", ActionRisk.MEDIUM)

    data class CancelTask(val taskId: String = "") : AndroidAction("cancel_task", ActionRisk.LOW)

    data class PlanAndExecuteTask(
        val prompt: String,
        val taskId: String = "",
    ) : AndroidAction("plan_and_execute_task", ActionRisk.MEDIUM)

    data class RememberMemory(
        val key: String,
        val value: String,
        val category: String = "PREFERENCE",
        val confirmed: Boolean = false,
    ) : AndroidAction("remember_memory", ActionRisk.LOW)

    data class ForgetMemory(
        val key: String,
        val category: String? = null,
    ) : AndroidAction("forget_memory", ActionRisk.LOW)

    data class QueryMemory(
        val query: String,
    ) : AndroidAction("query_memory", ActionRisk.LOW)

    // ── Expanded PC & OpenJarvis Functions ──────────────────────────────────
    data class EvaluateMath(
        val expression: String,
    ) : AndroidAction("evaluate_math", ActionRisk.LOW)

    data object GetDeviceDiagnostics : AndroidAction("get_device_diagnostics", ActionRisk.LOW)

    data class WebSearch(
        val query: String,
        val openInBrowser: Boolean = false,
    ) : AndroidAction("web_search", ActionRisk.LOW)

    data class GetWeather(
        val location: String? = null,
    ) : AndroidAction("get_weather", ActionRisk.LOW)

    data object GetDailyBriefing : AndroidAction("get_daily_briefing", ActionRisk.LOW)

    data class SetTimer(
        val seconds: Int,
        val label: String = "Timer",
    ) : AndroidAction("set_timer", ActionRisk.LOW)

    data class SetAlarm(
        val hour: Int,
        val minutes: Int,
        val label: String = "Alarm",
        val skipUi: Boolean = true,
    ) : AndroidAction("set_alarm", ActionRisk.MEDIUM)

    data object GetClipboard : AndroidAction("get_clipboard", ActionRisk.LOW)

    data class SetClipboard(
        val text: String,
    ) : AndroidAction("set_clipboard", ActionRisk.LOW)

    data class SendWhatsAppMessage(
        val recipient: String,
        val message: String,
        val confirmed: Boolean = false,
    ) : AndroidAction("send_whatsapp_message", ActionRisk.HIGH, requiresConfirmation = true)

    data class InspectStorage(
        val path: String? = null,
    ) : AndroidAction("inspect_storage", ActionRisk.LOW)

    data class SetVolume(
        val level: Int = 50,
        val percent: Int = level,
        val streamType: String = "media",
    ) : AndroidAction("set_volume", ActionRisk.LOW)

    data class SetRingerMode(
        val mode: String,
    ) : AndroidAction("set_ringer_mode", ActionRisk.LOW)

    data class ExecutePcCommand(
        val command: String,
        val parameters: Map<String, Any?> = emptyMap(),
        val confirmed: Boolean = false,
    ) : AndroidAction("execute_pc_command", ActionRisk.HIGH, requiresConfirmation = true)

    // OpenJarvis Specialized Tools
    data class ConvertCurrency(
        val amount: Double,
        val from: String,
        val to: String,
    ) : AndroidAction("convert_currency", ActionRisk.LOW)

    data class ReadFile(
        val path: String,
        val maxLines: Int = 100,
    ) : AndroidAction("read_file", ActionRisk.LOW)

    data class WriteFile(
        val path: String,
        val content: String,
        val append: Boolean = false,
        val confirmed: Boolean = false,
    ) : AndroidAction("write_file", ActionRisk.MEDIUM, requiresConfirmation = true)

    data class Think(
        val thought: String,
    ) : AndroidAction("think", ActionRisk.LOW)

    data class LookupKnowledge(
        val topic: String,
    ) : AndroidAction("lookup_knowledge", ActionRisk.LOW)
}
