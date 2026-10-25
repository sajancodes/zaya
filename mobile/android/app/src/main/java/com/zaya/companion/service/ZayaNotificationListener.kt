package com.zaya.companion.service

import android.app.Notification
import android.app.PendingIntent
import android.app.RemoteInput
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import com.zaya.companion.ZayaApp
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap

data class NotificationItem(
    val key: String,
    val packageName: String,
    val appName: String,
    val title: String,
    val text: String,
    val timestamp: Long,
    val canReply: Boolean,
    val isGroup: Boolean = false,
    val lines: List<String> = emptyList(),
    val contentIntent: PendingIntent? = null,
)

sealed class ReplyOutcome {
    data class Success(val appName: String, val recipient: String) : ReplyOutcome()
    data class NoRemoteInput(val appName: String, val contentIntent: PendingIntent?) : ReplyOutcome()
    data object NotificationNotFound : ReplyOutcome()
    data class Failed(val reason: String) : ReplyOutcome()
}

/**
 * Continuous background NotificationListenerService.
 * Captures WhatsApp, Instagram, Telegram & SMS notifications in real time,
 * maintains an in-memory bounded cache for voice queries and summaries,
 * and executes supported RemoteInput inline auto-replies.
 */
class ZayaNotificationListener : NotificationListenerService() {

    data class ReplyAction(
        val pendingIntent: PendingIntent,
        val remoteInputs: Array<RemoteInput>,
        val packageName: String,
        val recipient: String,
    )

    companion object {
        private const val TAG = "ZayaNotifListener"
        private const val MAX_CACHE_SIZE = 50

        private val replyActions = ConcurrentHashMap<String, ReplyAction>()
        private val recentNotifications = ConcurrentHashMap<String, NotificationItem>()
        private var instance: ZayaNotificationListener? = null

        fun isConnected(): Boolean = instance != null

        fun getFriendlyAppName(context: Context, packageName: String): String {
            return when {
                packageName.contains("whatsapp", ignoreCase = true) -> "WhatsApp"
                packageName.contains("telegram", ignoreCase = true) -> "Telegram"
                packageName.contains("instagram", ignoreCase = true) -> "Instagram"
                packageName.contains("messaging", ignoreCase = true) ||
                        packageName.contains("mms", ignoreCase = true) -> "Messages"
                packageName.contains("signal", ignoreCase = true) -> "Signal"
                packageName.contains("slack", ignoreCase = true) -> "Slack"
                packageName.contains("discord", ignoreCase = true) -> "Discord"
                packageName.contains("gm", ignoreCase = true) ||
                        packageName.contains("email", ignoreCase = true) -> "Gmail"
                else -> {
                    try {
                        val pm = context.packageManager
                        val info = pm.getApplicationInfo(packageName, 0)
                        pm.getApplicationLabel(info).toString()
                    } catch (e: Exception) {
                        packageName.substringAfterLast('.')
                            .replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }
                    }
                }
            }
        }

        /**
         * Returns active notifications matching optional package or sender filters.
         * Queries the live NotificationListenerService if connected, falling back
         * to the recent notifications cache.
         */
        fun getActiveNotifications(
            context: Context,
            packageFilter: String? = null,
            senderFilter: String? = null,
            limit: Int = 10
        ): List<NotificationItem> {
            val inst = instance
            if (inst != null) {
                try {
                    val sbns = inst.activeNotifications ?: emptyArray()
                    for (sbn in sbns) {
                        parseAndCache(context, sbn)
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "Failed to read live activeNotifications: ${e.message}")
                }
            }

            var items = recentNotifications.values.toList()

            // Filter out Zaya's own notifications
            items = items.filter { it.packageName != context.packageName }

            // Filter out empty notifications without sender or text
            items = items.filter { it.title.isNotBlank() || it.text.isNotBlank() || it.lines.isNotEmpty() }

            if (!packageFilter.isNullOrBlank()) {
                val cleanPkg = packageFilter.lowercase().trim()
                items = items.filter {
                    it.packageName.lowercase().contains(cleanPkg) ||
                            it.appName.lowercase().contains(cleanPkg)
                }
            }

            if (!senderFilter.isNullOrBlank()) {
                val cleanSender = senderFilter.lowercase().trim()
                items = items.filter { it.title.lowercase().contains(cleanSender) }
            }

            return items
                .sortedByDescending { it.timestamp }
                .take(limit)
        }

        /**
         * Finds the best matching notification for a reply operation.
         */
        fun findNotificationForReply(
            context: Context,
            targetKey: String? = null,
            targetSender: String? = null,
            targetPackage: String? = null
        ): NotificationItem? {
            val notifications = getActiveNotifications(
                context = context,
                packageFilter = targetPackage,
                senderFilter = targetSender,
                limit = 20
            )

            if (!targetKey.isNullOrBlank()) {
                return notifications.firstOrNull { it.key == targetKey }
            }

            if (!targetSender.isNullOrBlank()) {
                val clean = targetSender.lowercase().trim()
                val bySender = notifications.filter { it.title.lowercase().contains(clean) }
                if (bySender.isNotEmpty()) {
                    return bySender.first()
                }
            }

            return notifications.firstOrNull { it.canReply } ?: notifications.firstOrNull()
        }

        /**
         * Dispatches a RemoteInput reply to the targeted notification key.
         */
        fun sendReply(notificationKey: String, text: String): ReplyOutcome {
            val action = replyActions[notificationKey] ?: run {
                val cached = recentNotifications[notificationKey]
                return if (cached != null && !cached.canReply) {
                    ReplyOutcome.NoRemoteInput(cached.appName, cached.contentIntent)
                } else {
                    ReplyOutcome.NotificationNotFound
                }
            }

            val inst = instance ?: return ReplyOutcome.Failed("Notification listener is disconnected.")
            return try {
                val intent = Intent()
                val bundle = Bundle()
                for (remoteInput in action.remoteInputs) {
                    bundle.putCharSequence(remoteInput.resultKey, text)
                }
                RemoteInput.addResultsToIntent(action.remoteInputs, intent, bundle)
                action.pendingIntent.send(inst, 0, intent)
                Log.i(TAG, "RemoteInput reply dispatched successfully.")
                ReplyOutcome.Success(action.packageName, action.recipient)
            } catch (e: PendingIntent.CanceledException) {
                Log.e(TAG, "PendingIntent was canceled: ${e.message}")
                ReplyOutcome.Failed("Notification was dismissed or is no longer active.")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send auto-reply: ${e.message}")
                ReplyOutcome.Failed("Could not submit reply: ${e.message}")
            }
        }

        fun sendAutoReply(notificationKey: String, text: String): Boolean {
            return when (sendReply(notificationKey, text)) {
                is ReplyOutcome.Success -> true
                else -> false
            }
        }

        private fun parseAndCache(context: Context, sbn: StatusBarNotification): NotificationItem? {
            val pkg = sbn.packageName ?: return null
            if (pkg == context.packageName) return null

            val notif = sbn.notification ?: return null
            val extras = notif.extras ?: return null

            val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString()?.trim() ?: ""
            val text = (extras.getCharSequence(Notification.EXTRA_BIG_TEXT)
                ?: extras.getCharSequence(Notification.EXTRA_TEXT))?.toString()?.trim() ?: ""

            val linesArray = extras.getCharSequenceArray(Notification.EXTRA_TEXT_LINES)
            val lines = linesArray?.mapNotNull { it?.toString()?.trim() } ?: emptyList()

            // Skip silent ongoing events without messages (e.g. system download bars)
            val isOngoing = (notif.flags and Notification.FLAG_ONGOING_EVENT) != 0
            if (isOngoing && title.isBlank() && text.isBlank()) return null

            val appName = getFriendlyAppName(context, pkg)
            val key = sbn.key

            // Check and extract RemoteInput action
            var canReply = false
            notif.actions?.forEach { act ->
                val inputs = act.remoteInputs
                if (!inputs.isNullOrEmpty() && act.actionIntent != null) {
                    replyActions[key] = ReplyAction(act.actionIntent, inputs, appName, title)
                    canReply = true
                }
            }

            val isGroup = extras.getBoolean(Notification.EXTRA_IS_GROUP_CONVERSATION, false)
            val item = NotificationItem(
                key = key,
                packageName = pkg,
                appName = appName,
                title = title,
                text = text,
                timestamp = sbn.postTime,
                canReply = canReply,
                isGroup = isGroup,
                lines = lines,
                contentIntent = notif.contentIntent
            )

            recentNotifications[key] = item

            // Enforce bounded cache size
            if (recentNotifications.size > MAX_CACHE_SIZE) {
                val oldest = recentNotifications.values.minByOrNull { it.timestamp }
                if (oldest != null) {
                    recentNotifications.remove(oldest.key)
                    replyActions.remove(oldest.key)
                }
            }

            return item
        }
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        instance = this
        Log.i(TAG, "ZayaNotificationListener connected")
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        if (instance == this) instance = null
        Log.i(TAG, "ZayaNotificationListener disconnected")
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)
        if (sbn == null) return

        val item = parseAndCache(applicationContext, sbn) ?: return

        // Forward to runtime if connected
        val runtime = ZayaApp.runtime.value ?: return
        val payload = JSONObject().apply {
            put("key", item.key)
            put("package", item.packageName)
            put("app_name", item.appName)
            put("title", item.title)
            put("text", item.text)
            put("can_reply", item.canReply)
            put("timestamp", item.timestamp)
        }
        runtime.sendNotificationEvent(payload)
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        super.onNotificationRemoved(sbn)
        sbn?.key?.let { key ->
            recentNotifications.remove(key)
            replyActions.remove(key)
        }
    }
}
