package com.zaya.companion

import com.zaya.companion.action.ActionCapability
import com.zaya.companion.action.ActionRisk
import com.zaya.companion.action.ActionResult
import com.zaya.companion.action.ActionResultStatus
import com.zaya.companion.action.AndroidAction
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ActionEngineTest {

    @Test
    fun `action risk classification matches policy`() {
        val flashlight = AndroidAction.SetFlashlight(true)
        assertEquals(ActionRisk.LOW, flashlight.risk)
        assertFalse(flashlight.requiresConfirmation)

        val media = AndroidAction.ControlMedia("pause")
        assertEquals(ActionRisk.MEDIUM, media.risk)
        assertFalse(media.requiresConfirmation)

        val sms = AndroidAction.ComposeSms("1234567890", "Test message")
        assertEquals(ActionRisk.CRITICAL, sms.risk)
        assertTrue(sms.requiresConfirmation)

        val reply = AndroidAction.ReplyToNotification("key_123", "Reply text")
        assertEquals(ActionRisk.HIGH, reply.risk)
        assertTrue(reply.requiresConfirmation)
    }

    @Test
    fun `action result serialization produces expected JSON keys`() {
        val success = ActionResult.success("Flashlight turned on.", mapOf("state" to true))
        val json = success.toJsonObject()
        assertEquals("SUCCESS", json.getString("status"))
        assertEquals("Flashlight turned on.", json.getString("spoken_message"))
        assertTrue(json.getJSONObject("data").getBoolean("state"))

        val needsConfirm = ActionResult.needsConfirmation("Send text to John?", "compose_sms", mapOf("recipient" to "John"))
        val confirmJson = needsConfirm.toJsonObject()
        assertEquals("NEEDS_CONFIRMATION", confirmJson.getString("status"))
        assertEquals("compose_sms", confirmJson.getJSONObject("data").getString("action_id"))
        assertEquals("John", confirmJson.getJSONObject("data").getString("recipient"))

        val permReq = ActionResult.permissionRequired("android.permission.READ_CONTACTS")
        val permJson = permReq.toJsonObject()
        assertEquals("PERMISSION_REQUIRED", permJson.getString("status"))
        assertEquals("android.permission.READ_CONTACTS", permJson.getString("error"))

        val unsupported = ActionResult.unsupported("Screen gestures require Accessibility Service authorization.")
        val unsuppJson = unsupported.toJsonObject()
        assertEquals("UNSUPPORTED", unsuppJson.getString("status"))
        assertTrue(unsuppJson.getString("error").contains("Accessibility Service"))
    }

    @Test
    fun `action capability descriptor serializes correctly`() {
        val cap = ActionCapability(
            actionId = "set_flashlight",
            purpose = "Toggle camera LED flashlight",
            requiredArguments = listOf("enabled"),
            risk = ActionRisk.LOW,
            requiresConfirmation = false,
            isSupportedOnOs = true,
            isPermissionGranted = true,
            isAvailable = true,
        )

        val json = cap.toJsonObject()
        assertEquals("set_flashlight", json.getString("action_id"))
        assertEquals("LOW", json.getString("risk"))
        assertTrue(json.getBoolean("available"))
        assertEquals("enabled", json.getJSONArray("required_arguments").getString(0))
    }

    @Test
    fun `all supported action types have non-blank identifiers`() {
        val actions = listOf(
            AndroidAction.SetFlashlight(true),
            AndroidAction.OpenSystemSettings("wifi"),
            AndroidAction.ControlMedia("play"),
            AndroidAction.LaunchApp("Chrome"),
            AndroidAction.LookUpContact("Alice"),
            AndroidAction.InitiateCall("Alice"),
            AndroidAction.GetIncomingCallState,
            AndroidAction.SetCallerAnnouncement(true),
            AndroidAction.ComposeSms("123", "hi"),
            AndroidAction.AnswerCall,
            AndroidAction.RejectCall,
            AndroidAction.ReadNotifications(),
            AndroidAction.ReadLatestNotification(),
            AndroidAction.SummarizeNotifications(),
            AndroidAction.DraftNotificationReply(),
            AndroidAction.ReplyToNotification(notificationKey = "k", text = "txt"),
            AndroidAction.CaptureScreen,
            AndroidAction.DescribeScreen("what is this"),
            AndroidAction.ExtractVisibleText(),
            AndroidAction.SummarizeScreen(),
            AndroidAction.ScrollScreen("down"),
            AndroidAction.TapScreen(100f, 200f),
            AndroidAction.RunTask("task_1"),
            AndroidAction.CancelTask("task_1"),
        )

        for (action in actions) {
            assertTrue("Action ID must not be blank", action.actionId.isNotBlank())
            assertNotNull("Action risk must be defined", action.risk)
        }
    }
}
