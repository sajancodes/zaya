package com.zaya.companion.service

import android.app.Notification
import android.app.PendingIntent
import android.app.RemoteInput
import android.content.Intent
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.util.Log
import com.zaya.companion.ZayaApp
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap

/**
 * Continuous background NotificationListenerService.
 * Captures WhatsApp, Instagram, Telegram & SMS notifications in real time
 * and provides autonomous RemoteInput inline AI auto-replies.
 */
class ZayaNotificationListener : NotificationListenerService() {

    data class ReplyAction(
        val pendingIntent: PendingIntent,
        val remoteInputs: Array<RemoteInput>,
    )

    companion object {
        private const val TAG = "ZayaNotifListener"
        private val replyActions = ConcurrentHashMap<String, ReplyAction>()
        private var instance: ZayaNotificationListener? = null

        fun sendAutoReply(notificationKey: String, text: String): Boolean {
            val action = replyActions[notificationKey] ?: run {
                Log.w(TAG, "No cached RemoteInput action for key $notificationKey")
                return false
            }
            val inst = instance ?: return false
            return try {
                val intent = Intent()
                val bundle = Bundle()
                for (remoteInput in action.remoteInputs) {
                    bundle.putCharSequence(remoteInput.resultKey, text)
                }
                RemoteInput.addResultsToIntent(action.remoteInputs, intent, bundle)
                action.pendingIntent.send(inst, 0, intent)
                Log.i(TAG, "Autonomous inline auto-reply dispatched successfully!")
                true
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send auto-reply: ${e.message}")
                false
            }
        }
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        instance = this
        Log.i(TAG, "Notification listener connected")
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        if (instance == this) instance = null
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)
        if (sbn == null) return

        val pkg = sbn.packageName ?: ""
        // Target messaging apps
        val isTarget = pkg.contains("whatsapp", ignoreCase = true) ||
            pkg.contains("telegram", ignoreCase = true) ||
            pkg.contains("instagram", ignoreCase = true) ||
            pkg.contains("mms", ignoreCase = true) ||
            pkg.contains("messaging", ignoreCase = true)

        if (!isTarget) return

        val extras = sbn.notification?.extras ?: return
        val title = extras.getString(Notification.EXTRA_TITLE) ?: ""
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString()
            ?: extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString()
            ?: ""

        if (title.isEmpty() && text.isEmpty()) return

        // Extract RemoteInput action for autonomous inline reply
        val key = sbn.key
        sbn.notification?.actions?.forEach { act ->
            val inputs = act.remoteInputs
            if (!inputs.isNullOrEmpty() && act.actionIntent != null) {
                replyActions[key] = ReplyAction(act.actionIntent, inputs)
            }
        }

        val runtime = ZayaApp.runtime.value ?: return
        val payload = JSONObject().apply {
            put("key", key)
            put("package", pkg)
            put("title", title)
            put("text", text)
            put("can_reply", replyActions.containsKey(key))
            put("timestamp", System.currentTimeMillis())
        }

        runtime.sendNotificationEvent(payload)
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        super.onNotificationRemoved(sbn)
        sbn?.key?.let { replyActions.remove(it) }
    }
}
