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
    private var voiceForeground = false

    override fun onCreate() {
        super.onCreate()
        Notifications.ensureChannels(this)
        val created = ZayaRuntime(applicationContext, scope)
        runtime = created
        if (!startForegroundSafely(created.connection.value, created)) { stopSelf(); return }
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
            ACTION_VOICE_BEGIN -> {
                voiceForeground = true
                voiceReady = startForegroundSafely(current?.connection?.value ?: ConnectionStatus(), current, projectionReady)
            }
            ACTION_VOICE_END -> {
                voiceForeground = false
                voiceReady = false
                startForegroundSafely(current?.connection?.value ?: ConnectionStatus(), current, projectionReady)
            }
            ACTION_PROJECTION_BEGIN -> {
                projectionReady = startForegroundSafely(current?.connection?.value ?: ConnectionStatus(), current, true)
            }
            ACTION_PROJECTION_END -> {
                projectionReady = false
                startForegroundSafely(current?.connection?.value ?: ConnectionStatus(), current, false)
            }
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
        projectionReady = false
        voiceReady = false
        voiceForeground = false
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
                if (ringingCallId == effect.call.callId) return
                ringingCallId = effect.call.callId
                Ringer.start(this)
                Notifications.post(this, Notifications.ID_CALL, Notifications.incomingCall(this, effect.call))
                Notifications.showIncomingScreen(this, effect.call)
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
            RuntimeEffect.StartVoice, RuntimeEffect.StopVoice, RuntimeEffect.Ringback -> Unit
        }
    }

    private fun updateNotification(status: ConnectionStatus, source: ZayaRuntime) {
        val name = source.pairing.value?.serverName
            ?: source.model.serverName.value
        Notifications.post(this, Notifications.ID_CONNECTION, Notifications.connection(this, status, name))
        if (status.isOnline) {
            val active = source.model.call.value
            if (active !is CallUiState.Ringing && ringingCallId.isNotEmpty()) {
                Ringer.stop()
                Notifications.cancel(this, Notifications.ID_CALL)
                ringingCallId = ""
            }
        }
    }

    private fun startForegroundSafely(status: ConnectionStatus, source: ZayaRuntime?, projection: Boolean = false): Boolean {
        val notification = Notifications.connection(this, status, source?.pairing?.value?.serverName ?: "Zaya")
        val type = if (Build.VERSION.SDK_INT >= 29) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC or
                (if (Build.VERSION.SDK_INT >= 34) ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE else 0) or
                (if (projection) ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION else 0) or
                (if (voiceForeground && Build.VERSION.SDK_INT >= 30) ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE else 0)
        } else 0
        return runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
                startForeground(Notifications.ID_CONNECTION, notification, type)
            else startForeground(Notifications.ID_CONNECTION, notification)
            true
        }.getOrElse { android.util.Log.w("ZayaService", "Foreground service unavailable", it); false }
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
        @Volatile var voiceReady = false
            private set
        const val ACTION_VOICE_BEGIN = "com.zaya.companion.action.VOICE_BEGIN"
        const val ACTION_VOICE_END = "com.zaya.companion.action.VOICE_END"
        @Volatile var projectionReady = false
            private set
        const val ACTION_PROJECTION_BEGIN = "com.zaya.companion.action.PROJECTION_BEGIN"
        const val ACTION_PROJECTION_END = "com.zaya.companion.action.PROJECTION_END"
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
