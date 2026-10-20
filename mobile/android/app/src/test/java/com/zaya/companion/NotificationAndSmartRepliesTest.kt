package com.zaya.companion

import com.zaya.companion.action.ActionRisk
import com.zaya.companion.action.ActionResult
import com.zaya.companion.action.ActionResultStatus
import com.zaya.companion.action.AndroidAction
import com.zaya.companion.service.NotificationItem
import com.zaya.companion.service.ReplyOutcome
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NotificationAndSmartRepliesTest {

    @Test
    fun `read notifications actions have low risk and no confirmation`() {
        val readAll = AndroidAction.ReadNotifications()
        assertEquals("read_notifications", readAll.actionId)
        assertEquals(ActionRisk.LOW, readAll.risk)
        assertFalse(readAll.requiresConfirmation)

        val readLatest = AndroidAction.ReadLatestNotification("com.whatsapp")
        assertEquals("read_latest_notification", readLatest.actionId)
        assertEquals(ActionRisk.LOW, readLatest.risk)
        assertEquals("com.whatsapp", readLatest.packageFilter)

        val summarize = AndroidAction.SummarizeNotifications()
        assertEquals("summarize_notifications", summarize.actionId)
        assertEquals(ActionRisk.LOW, summarize.risk)
    }

    @Test
    fun `draft notification reply action has low risk and captures target context`() {
        val draft = AndroidAction.DraftNotificationReply(
            targetSender = "Alex",
            targetPackage = "whatsapp",
            contextInstruction = "Tell them I'll be there in 5"
        )
        assertEquals("draft_notification_reply", draft.actionId)
        assertEquals(ActionRisk.LOW, draft.risk)
        assertFalse(draft.requiresConfirmation)
        assertEquals("Alex", draft.targetSender)
        assertEquals("whatsapp", draft.targetPackage)
    }

    @Test
    fun `reply to notification action requires confirmation and has high risk`() {
        val reply = AndroidAction.ReplyToNotification(
            notificationKey = "key_whatsapp_101",
            targetSender = "Alex",
            text = "On my way!",
            confirmed = false
        )
        assertEquals("reply_notification", reply.actionId)
        assertEquals(ActionRisk.HIGH, reply.risk)
        assertTrue(reply.requiresConfirmation)
        assertEquals("On my way!", reply.text)
        assertFalse(reply.confirmed)
    }

    @Test
    fun `notification item correctly tracks replyability and group state`() {
        val singleItem = NotificationItem(
            key = "item_1",
            packageName = "com.whatsapp",
            appName = "WhatsApp",
            title = "Sarah",
            text = "Are you coming?",
            timestamp = 1700000000000L,
            canReply = true,
            isGroup = false
        )
        assertEquals("item_1", singleItem.key)
        assertEquals("WhatsApp", singleItem.appName)
        assertEquals("Sarah", singleItem.title)
        assertTrue(singleItem.canReply)
        assertFalse(singleItem.isGroup)

        val groupItem = NotificationItem(
            key = "item_2",
            packageName = "org.telegram.messenger",
            appName = "Telegram",
            title = "Family Group",
            text = "Dinner at 7",
            timestamp = 1700000005000L,
            canReply = true,
            isGroup = true,
            lines = listOf("Mom: Dinner at 7", "Dad: Perfect")
        )
        assertTrue(groupItem.isGroup)
        assertEquals(2, groupItem.lines.size)
    }

    @Test
    fun `reply outcome distinguishes success from missing remote input or dismissal`() {
        val success = ReplyOutcome.Success("WhatsApp", "Sarah")
        assertEquals("WhatsApp", success.appName)
        assertEquals("Sarah", success.recipient)

        val noInput = ReplyOutcome.NoRemoteInput("Instagram", null)
        assertEquals("Instagram", noInput.appName)

        val notFound = ReplyOutcome.NotificationNotFound
        assertTrue(notFound is ReplyOutcome)

        val failed = ReplyOutcome.Failed("PendingIntent was canceled")
        assertEquals("PendingIntent was canceled", failed.reason)
    }

    @Test
    fun `notification access disabled result directs to settings flow`() {
        val result = ActionResult.failure(
            spoken = "Notification access is not enabled. Would you like me to open settings?",
            error = "notification_access_disabled",
            data = mapOf("needs_settings" to "notification_listener")
        )
        val json = result.toJsonObject()
        assertEquals("FAILED", json.getString("status"))
        assertEquals("notification_access_disabled", json.getString("error"))
        assertEquals("notification_listener", json.getJSONObject("data").getString("needs_settings"))
    }

    @Test
    fun `smart reply confirmation serialization contains expected recipient and text`() {
        val confirm = ActionResult.needsConfirmation(
            spoken = "Do you want me to reply to Alex on WhatsApp: \"Sounds good!\"?",
            actionId = "reply_notification",
            payload = mapOf(
                "notification_key" to "key_101",
                "sender" to "Alex",
                "app" to "WhatsApp",
                "text" to "Sounds good!"
            )
        )
        val json = confirm.toJsonObject()
        assertEquals("NEEDS_CONFIRMATION", json.getString("status"))
        val data = json.getJSONObject("data")
        assertEquals("Alex", data.getString("sender"))
        assertEquals("WhatsApp", data.getString("app"))
        assertEquals("Sounds good!", data.getString("text"))
        assertEquals("reply_notification", data.getString("action_id"))
    }

    @Test
    fun `summarize notifications result includes total count and apps`() {
        val summaryResult = ActionResult.success(
            spoken = "You have 3 notifications: 2 from WhatsApp and 1 from Telegram.",
            data = mapOf(
                "total_count" to 3,
                "apps" to mapOf("WhatsApp" to 2, "Telegram" to 1)
            )
        )
        val json = summaryResult.toJsonObject()
        assertEquals("SUCCESS", json.getString("status"))
        assertEquals(3, json.getJSONObject("data").getInt("total_count"))
    }
}
