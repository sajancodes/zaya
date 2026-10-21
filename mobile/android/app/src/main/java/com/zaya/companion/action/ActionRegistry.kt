package com.zaya.companion.action

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.content.ContextCompat
import org.json.JSONArray
import org.json.JSONObject

/**
 * Descriptor of a registered capability on this Android device.
 */
data class ActionCapability(
    val actionId: String,
    val purpose: String,
    val requiredArguments: List<String>,
    val risk: ActionRisk,
    val requiresConfirmation: Boolean,
    val isSupportedOnOs: Boolean,
    val isPermissionGranted: Boolean,
    val isAvailable: Boolean,
) {
    fun toJsonObject(): JSONObject = JSONObject().apply {
        put("action_id", actionId)
        put("purpose", purpose)
        put("required_arguments", JSONArray(requiredArguments))
        put("risk", risk.name)
        put("requires_confirmation", requiresConfirmation)
        put("supported_on_os", isSupportedOnOs)
        put("permission_granted", isPermissionGranted)
        put("available", isAvailable)
    }
}

/**
 * Central registry and capability discovery engine for IRIS Android phone control.
 */
class ActionRegistry(private val context: Context) {

    fun hasPermission(permission: String): Boolean {
        return ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED
    }

    private fun hasFlashlightHardware(): Boolean {
        return context.packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_FLASH)
    }

    private fun isNotificationListenerEnabled(): Boolean {
        val flat = android.provider.Settings.Secure.getString(
            context.contentResolver,
            "enabled_notification_listeners"
        ) ?: return false
        return flat.contains(context.packageName)
    }

    fun discoverCapabilities(): List<ActionCapability> {
        val list = mutableListOf<ActionCapability>()

        list.add(ActionCapability("set_volume", "Set phone media volume percent", listOf("percent"),
            ActionRisk.LOW, false, true, true, true))
        // 1. Launch App
        list.add(
            ActionCapability(
                actionId = "launch_app",
                purpose = "Launch installed application or deep link by name",
                requiredArguments = listOf("name"),
                risk = ActionRisk.MEDIUM,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = true,
                isAvailable = true,
            )
        )

        // 2. Set Flashlight
        val hasFlash = hasFlashlightHardware()
        list.add(
            ActionCapability(
                actionId = "set_flashlight",
                purpose = "Toggle camera LED flashlight on or off",
                requiredArguments = listOf("enabled"),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = true,
                isAvailable = hasFlash,
            )
        )

        // 3. Open System Settings
        list.add(
            ActionCapability(
                actionId = "open_settings",
                purpose = "Navigate to system settings panels (Wi-Fi, Bluetooth, Hotspot, Location)",
                requiredArguments = listOf("setting"),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = true,
                isAvailable = true,
            )
        )

        // 4. Media Controls
        list.add(
            ActionCapability(
                actionId = "control_media",
                purpose = "Control media playback (play, pause, toggle, next, previous)",
                requiredArguments = listOf("action"),
                risk = ActionRisk.MEDIUM,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = true,
                isAvailable = true,
            )
        )

        // 5. Look Up Contact
        val hasContacts = hasPermission(Manifest.permission.READ_CONTACTS)
        list.add(ActionCapability("browse_media", "Find or open phone photos, videos and audio on request",
            listOf("kind"), ActionRisk.LOW, false, true,
            if (Build.VERSION.SDK_INT >= 33) hasPermission(Manifest.permission.READ_MEDIA_IMAGES)
            else hasPermission(Manifest.permission.READ_EXTERNAL_STORAGE), true))
        list.add(
            ActionCapability(
                actionId = "lookup_contact",
                purpose = "Search device contacts directory by name",
                requiredArguments = listOf("query"),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = hasContacts,
                isAvailable = hasContacts,
            )
        )

        // 5b. Initiate Call
        val hasCallPhone = hasPermission(Manifest.permission.CALL_PHONE)
        list.add(
            ActionCapability(
                actionId = "initiate_call",
                purpose = "Place a phone call directly or open system dialer for a contact",
                requiredArguments = listOf("query"),
                risk = ActionRisk.HIGH,
                requiresConfirmation = true,
                isSupportedOnOs = true,
                isPermissionGranted = hasCallPhone,
                isAvailable = true,
            )
        )

        // 5c. Get Incoming Call State
        val hasPhoneState = hasPermission(Manifest.permission.READ_PHONE_STATE)
        list.add(
            ActionCapability(
                actionId = "get_incoming_call_state",
                purpose = "Check if phone is currently ringing and identify caller",
                requiredArguments = emptyList(),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = hasPhoneState,
                isAvailable = true,
            )
        )

        // 5d. Set Caller Announcement
        list.add(
            ActionCapability(
                actionId = "set_caller_announcement",
                purpose = "Enable or disable automatic TTS incoming caller announcements",
                requiredArguments = listOf("enabled"),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = true,
                isAvailable = true,
            )
        )

        // 6. Compose SMS
        list.add(
            ActionCapability(
                actionId = "compose_sms",
                purpose = "Compose and dispatch text SMS to a contact",
                requiredArguments = listOf("recipient", "message"),
                risk = ActionRisk.CRITICAL,
                requiresConfirmation = true,
                isSupportedOnOs = true,
                isPermissionGranted = hasPermission(Manifest.permission.SEND_SMS),
                isAvailable = true,
            )
        )

        // 7. Answer Call
        val answerSupported = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
        val answerPerm = hasPermission(Manifest.permission.ANSWER_PHONE_CALLS)
        list.add(
            ActionCapability(
                actionId = "answer_call",
                purpose = "Answer an incoming ringing cellular phone call hands-free",
                requiredArguments = emptyList(),
                risk = ActionRisk.HIGH,
                requiresConfirmation = false,
                isSupportedOnOs = answerSupported,
                isPermissionGranted = answerPerm,
                isAvailable = answerSupported && answerPerm,
            )
        )

        // 8. Reject Call
        val rejectSupported = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P
        val rejectPerm = hasPermission(Manifest.permission.ANSWER_PHONE_CALLS)
        list.add(
            ActionCapability(
                actionId = "reject_call",
                purpose = "Decline or reject an incoming cellular call",
                requiredArguments = emptyList(),
                risk = ActionRisk.HIGH,
                requiresConfirmation = false,
                isSupportedOnOs = rejectSupported,
                isPermissionGranted = rejectPerm,
                isAvailable = rejectSupported && rejectPerm,
            )
        )

        // 9. Read Notifications
        val notifAccess = isNotificationListenerEnabled()
        list.add(
            ActionCapability(
                actionId = "read_notifications",
                purpose = "Read recent messaging notifications with optional app or sender filter",
                requiredArguments = emptyList(),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = notifAccess,
                isAvailable = notifAccess,
            )
        )

        // 9b. Read Latest Notification
        list.add(
            ActionCapability(
                actionId = "read_latest_notification",
                purpose = "Read the most recent incoming notification aloud",
                requiredArguments = emptyList(),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = notifAccess,
                isAvailable = notifAccess,
            )
        )

        // 9c. Summarize Notifications
        list.add(
            ActionCapability(
                actionId = "summarize_notifications",
                purpose = "Summarize active notifications grouped by application",
                requiredArguments = emptyList(),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = notifAccess,
                isAvailable = notifAccess,
            )
        )

        // 9d. Draft Notification Reply
        list.add(
            ActionCapability(
                actionId = "draft_notification_reply",
                purpose = "Generate or draft an inline reply for an incoming message",
                requiredArguments = emptyList(),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = notifAccess,
                isAvailable = notifAccess,
            )
        )

        // 10. Reply to Notification
        list.add(
            ActionCapability(
                actionId = "reply_notification",
                purpose = "Send autonomous RemoteInput inline reply to a notification",
                requiredArguments = listOf("text"),
                risk = ActionRisk.HIGH,
                requiresConfirmation = true,
                isSupportedOnOs = true,
                isPermissionGranted = notifAccess,
                isAvailable = notifAccess,
            )
        )

        // 11. Screen Understanding (MediaProjection)
        val hasProjectionConsent = com.zaya.companion.service.ScreenCaptureManager.hasConsent()
        list.add(
            ActionCapability(
                actionId = "capture_screen",
                purpose = "Capture screen frame via MediaProjection consent",
                requiredArguments = emptyList(),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = hasProjectionConsent,
                isAvailable = true,
            )
        )
        list.add(
            ActionCapability(
                actionId = "describe_screen",
                purpose = "Analyze and explain what is visible on the screen",
                requiredArguments = emptyList(),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = hasProjectionConsent,
                isAvailable = true,
            )
        )
        list.add(
            ActionCapability(
                actionId = "extract_visible_text",
                purpose = "Extract visible text and error messages from the screen",
                requiredArguments = emptyList(),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = hasProjectionConsent,
                isAvailable = true,
            )
        )
        list.add(
            ActionCapability(
                actionId = "summarize_screen",
                purpose = "Summarize active page or application currently on screen",
                requiredArguments = emptyList(),
                risk = ActionRisk.LOW,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = hasProjectionConsent,
                isAvailable = true,
            )
        )

        // 12. Screen Gestures (Scroll/Tap) - requires AccessibilityService
        list.add(
            ActionCapability(
                actionId = "scroll_screen",
                purpose = "User-directed UI scrolling (Requires Accessibility Service)",
                requiredArguments = listOf("direction"),
                risk = ActionRisk.MEDIUM,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = false,
                isAvailable = false,
            )
        )
        list.add(
            ActionCapability(
                actionId = "tap_screen",
                purpose = "Direct screen coordinate touch gesture (Requires Accessibility Service)",
                requiredArguments = listOf("x", "y"),
                risk = ActionRisk.MEDIUM,
                requiresConfirmation = false,
                isSupportedOnOs = true,
                isPermissionGranted = false,
                isAvailable = false,
            )
        )

        return list
    }
}
