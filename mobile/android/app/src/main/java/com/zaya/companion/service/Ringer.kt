package com.zaya.companion.service

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log

/**
 * The ring itself.
 *
 * A real call rings until it is answered, declined or missed — a single
 * notification chime is not a phone call. This loops the phone's own ringtone
 * and repeats a vibration for exactly as long as the laptop says the call is
 * ringing.
 *
 * The laptop decides *that* the phone rings; the phone's ringer mode decides
 * *how*. Normal rings and shakes, vibrate-only shakes, silent stays silent —
 * a setting the owner chose is never overridden. A lost connection cannot leave
 * it ringing forever: the ring stops on its own a little after the laptop's own
 * ring window closes.
 */
object Ringer {
    private const val TAG = "ZayaRinger"
    private const val RING_CAP_MS = 60_000L
    private val PATTERN = longArrayOf(0L, 900L, 700L)

    private val handler = Handler(Looper.getMainLooper())
    private var active = false
    private var player: MediaPlayer? = null
    private var vibrator: Vibrator? = null

    private val cap = Runnable { stop() }

    /** Starts a call ring, honouring the phone's ringer mode. Idempotent. */
    fun start(context: Context) {
        if (active) return
        active = true
        when (context.getSystemService(AudioManager::class.java)?.ringerMode) {
            AudioManager.RINGER_MODE_SILENT -> return
            AudioManager.RINGER_MODE_VIBRATE -> vibrate(context)
            else -> {
                vibrate(context)
                sound(context)
            }
        }
        handler.postDelayed(cap, RING_CAP_MS)
    }

    /** Stops the ring and the vibration. Safe to call when nothing is ringing. */
    fun stop() {
        handler.removeCallbacks(cap)
        if (!active) return
        active = false
        runCatching { player?.stop() }
        runCatching { player?.release() }
        player = null
        runCatching { vibrator?.cancel() }
        vibrator = null
    }

    private fun sound(context: Context) {
        val uri = RingtoneManager.getActualDefaultRingtoneUri(context, RingtoneManager.TYPE_RINGTONE)
            ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
            ?: return
        runCatching {
            val created = MediaPlayer()
            created.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build(),
            )
            created.isLooping = true
            created.setDataSource(context, uri)
            created.setOnPreparedListener { prepared -> if (active) runCatching { prepared.start() } }
            created.setOnErrorListener { _, _, _ -> true }
            created.prepareAsync()
            player = created
        }.onFailure { Log.w(TAG, "Ringtone unavailable", it) }
    }

    private fun vibrate(context: Context) {
        val device = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            context.getSystemService(VibratorManager::class.java)?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Vibrator::class.java)
        } ?: return
        vibrator = device
        runCatching {
            // repeat = 0: shake, pause, and start the pattern again.
            device.vibrate(VibrationEffect.createWaveform(PATTERN, 0))
        }.onFailure { Log.w(TAG, "Vibration unavailable", it) }
    }
}
