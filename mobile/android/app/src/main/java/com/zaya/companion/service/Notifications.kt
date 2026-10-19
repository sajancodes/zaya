package com.zaya.companion.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.zaya.companion.MainActivity
import com.zaya.companion.R
import com.zaya.companion.protocol.CallInfo
import com.zaya.companion.protocol.ConnectionPhase
import com.zaya.companion.protocol.ConnectionStatus
import com.zaya.companion.protocol.NotificationItem
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.ui.IncomingCallActivity

/**
 * Notifications, and the rules about which ones may interrupt the owner.
 *
 * The priority scale is the laptop's, not the phone's: P0/P1 ring, P2 tells,
 * P3 is deliberately silent. A missed call produces exactly one summary line,
 * never a stream of redials.
 */
object Notifications {
    const val CHANNEL_CONNECTION = "zaya.connection"
    const val CHANNEL_CALLS = "zaya.calls"
    const val CHANNEL_MESSAGES = "zaya.messages"
    const val CHANNEL_MISSED = "zaya.missed"

    const val ID_CONNECTION = 1001
    const val ID_CALL = 1002

    fun ensureChannels(context: Context) {
        val manager = context.getSystemService(NotificationManager::class.java) ?: return
        manager.createNotificationChannels(
            listOf(
                NotificationChannel(
                    CHANNEL_CONNECTION,
                    context.getString(R.string.channel_connection),
                    NotificationManager.IMPORTANCE_MIN,
                ).apply {
                    description = context.getString(R.string.channel_connection_desc)
                    setShowBadge(false)
                    enableVibration(false)
                    setSound(null, null)
                },
                NotificationChannel(
                    CHANNEL_CALLS,
                    context.getString(R.string.channel_calls),
                    NotificationManager.IMPORTANCE_HIGH,
                ).apply {
                    description = context.getString(R.string.channel_calls_desc)
                    enableVibration(true)
                    vibrationPattern = longArrayOf(0, 600, 600, 600)
                    setShowBadge(true)
                },
                NotificationChannel(
                    CHANNEL_MESSAGES,
                    context.getString(R.string.channel_messages),
                    NotificationManager.IMPORTANCE_DEFAULT,
                ).apply {
                    description = context.getString(R.string.channel_messages_desc)
                    enableVibration(false)
                },
                // Deliberately quiet: a missed call is information, not an event.
                NotificationChannel(
                    CHANNEL_MISSED,
                    context.getString(R.string.channel_missed),
                    NotificationManager.IMPORTANCE_LOW,
                ).apply {
                    description = context.getString(R.string.channel_missed_desc)
                    enableVibration(false)
                    setSound(null, null)
                },
            ),
        )
    }

    fun connection(context: Context, status: ConnectionStatus, serverName: String): Notification {
        val text = when (status.phase) {
            ConnectionPhase.ONLINE -> context.getString(R.string.notif_connected)
            ConnectionPhase.CONNECTING -> context.getString(R.string.notif_connecting)
            ConnectionPhase.OFFLINE -> if (status.retryInSeconds > 0) {
                "${context.getString(R.string.notif_offline)} in ${status.retryInSeconds}s"
            } else {
                status.detail.ifBlank { context.getString(R.string.notif_offline) }
            }

            ConnectionPhase.UNPAIRED -> context.getString(R.string.notif_unpaired)
            ConnectionPhase.REVOKED -> context.getString(R.string.notif_revoked)
            ConnectionPhase.INCOMPATIBLE -> status.detail
        }
        val builder = NotificationCompat.Builder(context, CHANNEL_CONNECTION)
            .setSmallIcon(R.drawable.ic_zaya_notification)
            .setContentTitle(serverName)
            .setContentText(text)
            .setOngoing(true)
            .setSilent(true)
            .setShowWhen(false)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setContentIntent(openApp(context))
            .addAction(
                0,
                context.getString(R.string.action_reconnect),
                serviceAction(context, ZayaService.ACTION_RECONNECT, 21),
            )
        if (status.phase != ConnectionPhase.ONLINE) {
            builder.addAction(
                0,
                context.getString(R.string.action_disconnect),
                serviceAction(context, ZayaService.ACTION_DISCONNECT, 22),
            )
        }
        return builder.build()
    }

    fun incomingCall(context: Context, call: CallInfo): Notification {
        val title = call.title.ifBlank { context.getString(R.string.call_ringing) }
        val body = call.detail.ifBlank { call.reason }
        val fullScreen = PendingIntent.getActivity(
            context,
            31,
            Intent(context, IncomingCallActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                .putExtra(IncomingCallActivity.EXTRA_CALL_ID, call.callId),
            pendingFlags(),
        )
        return NotificationCompat.Builder(context, CHANNEL_CALLS)
            .setSmallIcon(R.drawable.ic_zaya_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setOngoing(true)
            .setAutoCancel(false)
            .setWhen(System.currentTimeMillis())
            .setShowWhen(false)
            .setContentIntent(fullScreen)
            .setFullScreenIntent(fullScreen, true)
            .addAction(
                0,
                context.getString(R.string.action_answer),
                serviceAction(context, ZayaService.ACTION_ANSWER, 32, call.callId),
            )
            .addAction(
                0,
                context.getString(R.string.action_decline),
                serviceAction(context, ZayaService.ACTION_DECLINE, 33, call.callId),
            )
            .build()
    }

    /** Everything the laptop asked the owner to see, priority honoured. */
    fun ownerMessage(context: Context, item: NotificationItem): Notification {
        val isMissed = item.title.contains("Missed", ignoreCase = true)
        val channel = if (isMissed) CHANNEL_MISSED else CHANNEL_MESSAGES
        val builder = NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.drawable.ic_zaya_notification)
            .setContentTitle(item.title.ifBlank { "Zaya" })
            .setContentText(item.body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(item.body))
            .setAutoCancel(true)
            .setWhen(item.at)
            .setShowWhen(true)
            .setContentIntent(openApp(context, item.source))
        if (item.quiet) {
            builder.setSilent(true).setPriority(NotificationCompat.PRIORITY_LOW)
        } else {
            builder.setPriority(NotificationCompat.PRIORITY_DEFAULT)
        }
        if (item.severity == "critical" || item.priority <= Protocol.P0_CRITICAL) {
            builder.setPriority(NotificationCompat.PRIORITY_HIGH)
        }
        if (item.body.isNotBlank()) {
            builder.addAction(0, context.getString(R.string.action_open), openApp(context, item.source))
        }
        return builder.build()
    }

    fun post(context: Context, id: Int, notification: Notification) {
        runCatching {
            NotificationManagerCompat.from(context).notify(id, notification)
        }.onFailure {
            // POST_NOTIFICATIONS refused: the in-app list still has everything.
        }
    }

    fun cancel(context: Context, id: Int) {
        runCatching { NotificationManagerCompat.from(context).cancel(id) }
    }

    private fun openApp(context: Context, source: String = ""): PendingIntent =
        PendingIntent.getActivity(
            context,
            40,
            Intent(context, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                .putExtra(MainActivity.EXTRA_OPEN, source),
            pendingFlags(),
        )

    private fun serviceAction(
        context: Context,
        action: String,
        requestCode: Int,
        callId: String = "",
    ): PendingIntent = PendingIntent.getService(
        context,
        requestCode,
        Intent(context, ZayaService::class.java)
            .setAction(action)
            .putExtra(ZayaService.EXTRA_CALL_ID, callId),
        pendingFlags(),
    )

    private fun pendingFlags(): Int =
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
}
