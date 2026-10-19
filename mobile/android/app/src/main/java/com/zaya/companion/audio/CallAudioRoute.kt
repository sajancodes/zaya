package com.zaya.companion.audio

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build

/** Own the phone's communication route only for the lifetime of a call. */
class CallAudioRoute(context: Context) {
    private val audio = context.getSystemService(AudioManager::class.java)
    private var oldMode: Int? = null
    private var oldSpeaker = false
    private var tone: ToneGenerator? = null
    private val focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
        .setAudioAttributes(AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
        .build()

    @Synchronized
    fun begin() {
        if (oldMode != null) return
        oldMode = audio.mode
        @Suppress("DEPRECATION")
        oldSpeaker = audio.isSpeakerphoneOn
        audio.mode = AudioManager.MODE_IN_COMMUNICATION
        audio.requestAudioFocus(focus)
        setSpeaker(false)
    }

    @Synchronized
    fun setSpeaker(enabled: Boolean): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val kind = if (enabled) AudioDeviceInfo.TYPE_BUILTIN_SPEAKER else AudioDeviceInfo.TYPE_BUILTIN_EARPIECE
            val device = audio.availableCommunicationDevices.firstOrNull { it.type == kind }
            if (device != null) audio.setCommunicationDevice(device)
            else if (!enabled) audio.clearCommunicationDevice()
            return audio.communicationDevice?.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER
        }
        @Suppress("DEPRECATION")
        run { audio.isSpeakerphoneOn = enabled; return audio.isSpeakerphoneOn }
    }

    @Synchronized
    fun ringback() {
        if (tone != null) return
        begin()
        tone = ToneGenerator(AudioManager.STREAM_VOICE_CALL, 55).also {
            it.startTone(ToneGenerator.TONE_SUP_RINGTONE)
        }
    }

    @Synchronized
    fun stopRinging() {
        tone?.stopTone()
        tone?.release()
        tone = null
    }

    @Synchronized
    fun end() {
        stopRinging()
        val mode = oldMode ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) audio.clearCommunicationDevice()
        else {
            @Suppress("DEPRECATION")
            run { audio.isSpeakerphoneOn = oldSpeaker }
        }
        audio.abandonAudioFocusRequest(focus)
        audio.mode = mode
        oldMode = null
    }
}
