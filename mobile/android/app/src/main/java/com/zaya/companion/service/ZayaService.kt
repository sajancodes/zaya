package com.zaya.companion.service

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.content.ContextCompat
import com.zaya.companion.ZayaApp
import com.zaya.companion.protocol.CallUiState
import com.zaya.companion.protocol.ConnectionStatus
import com.zaya.companion.runtime.RuntimeEffect
import com.zaya.companion.runtime.ZayaRuntime
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

/**
 * Keeps the phone paired and reachable while the app is not on screen.
 *
 * Zaya calls the phone, not the other way round, so the link has to outlive the
 * UI: this service owns the runtime, mirrors its state into one ongoing
 * notification, and turns the runtime's effects into rings and messages.
 */
class ZayaService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    var runtime: ZayaRuntime? = null
        private set

    private var watchers: Job? = null
    private var ringingCallId: String = ""

    override fun onCreate() {
        super.onCreate()
        Notifications.ensureChannels(this)
        val created = ZayaRuntime(applicationContext, scope)
        runtime = created
        startForegroundSafely(created.connection.value, created)
        ZayaApp.attach(created)
        created.start()
        watchers = scope.launch {
            launch {
                created.connection.collectLatest { status -> updateNotification(status, created) }
            }
            launch {
                created.effects.collect { effect -> handle(effect, created) }
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val current = runtime
        when (intent?.action) {
            ACTION_RECONNECT -> current?.reconnectNow()
            ACTION_DISCONNECT -> {
                current?.stop()
                stopForegroundCompat()
                stopSelf()
            }

            ACTION_ANSWER -> {
                val callId = intent.getStringExtra(EXTRA_CALL_ID).orEmpty()
                if (callId.isNotEmpty()) {
                    current?.answer(callId)
                    Notifications.cancel(this, Notifications.ID_CALL)
                    ringingCallId = ""
                }
                Ringer.stop()
            }

            ACTION_DECLINE -> {
                val callId = intent.getStringExtra(EXTRA_CALL_ID).orEmpty()
                if (callId.isNotEmpty()) current?.decline(callId)
                Notifications.cancel(this, Notifications.ID_CALL)
                ringingCallId = ""
                Ringer.stop()
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        Ringer.stop()
        Notifications.cancel(this, Notifications.ID_CALL)
        watchers?.cancel()
        runtime?.stop()
        scope.cancel()
        ZayaApp.detach(runtime)
        runtime = null
        super.onDestroy()
    }

    // ── wiring ───────────────────────────────────────────────────────────────

    private suspend fun handle(effect: RuntimeEffect, source: ZayaRuntime) {
        when (effect) {
            is RuntimeEffect.Ring -> {
                ringingCallId = effect.call.callId
                Ringer.start(this)
                Notifications.post(this, Notifications.ID_CALL, Notifications.incomingCall(this, effect.call))
            }

            RuntimeEffect.StopRinging -> {
                Ringer.stop()
                if (ringingCallId.isNotEmpty()) {
                    Notifications.cancel(this, Notifications.ID_CALL)
                    ringingCallId = ""
                }
            }

            is RuntimeEffect.Notify -> {
                val id = NOTIFICATION_BASE + (effect.item.key.hashCode() and 0xFFFF)
                Notifications.post(this, id, Notifications.ownerMessage(this, effect.item))
            }

            // Voice itself is handled inside the runtime, which owns the devices.
            RuntimeEffect.StartVoice, RuntimeEffect.StopVoice -> Unit
        }
    }

    private fun updateNotification(status: ConnectionStatus, source: ZayaRuntime) {
        val name = source.pairing.value?.serverName
            ?: source.model.serverName.value
        runCatching {
            androidx.core.app.NotificationManagerCompat.from(this)
                .notify(Notifications.ID_CONNECTION, Notifications.connection(this, status, name))
        }
        if (status.isOnline) {
            val active = source.model.call.value
            if (active !is CallUiState.Ringing && ringingCallId.isNotEmpty()) {
                Ringer.stop()
                Notifications.cancel(this, Notifications.ID_CALL)
                ringingCallId = ""
            }
        }
    }

    private fun startForegroundSafely(status: ConnectionStatus, source: ZayaRuntime) {
        val notification = Notifications.connection(
            this,
            status,
            source.pairing.value?.serverName ?: "Zaya",
        )
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC or
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE or
                ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE
        } else {
            0
        }
        runCatching {
            if (type == 0) {
                startForeground(Notifications.ID_CONNECTION, notification)
            } else {
                startForeground(Notifications.ID_CONNECTION, notification, type)
            }
        }.onFailure {
            // A foreground start can be refused (background start restrictions).
            // The service still runs while the app is alive; the owner can reopen
            // the app to re-establish the ongoing notification.
        }
    }

    private fun stopForegroundCompat() {
        runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                stopForeground(STOP_FOREGROUND_REMOVE)
            } else {
                @Suppress("DEPRECATION")
                stopForeground(true)
            }
        }
    }

    companion object {
        const val ACTION_RECONNECT = "com.zaya.companion.action.RECONNECT"
        const val ACTION_DISCONNECT = "com.zaya.companion.action.DISCONNECT"
        const val ACTION_ANSWER = "com.zaya.companion.action.ANSWER"
        const val ACTION_DECLINE = "com.zaya.companion.action.DECLINE"
        const val EXTRA_CALL_ID = "call_id"

        private const val NOTIFICATION_BASE = 2000

        /** Starts (or reuses) the foreground service that holds the connection. */
        fun ensureRunning(context: Context) {
            val intent = Intent(context, ZayaService::class.java)
            runCatching { ContextCompat.startForegroundService(context, intent) }
        }

        fun request(context: Context, action: String, callId: String = "") {
            val intent = Intent(context, ZayaService::class.java)
                .setAction(action)
                .putExtra(EXTRA_CALL_ID, callId)
            runCatching { context.startService(intent) }
        }
    }
}
