package com.zaya.companion.audio

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale
import java.util.UUID

sealed class VoiceOutputState {
    data object Idle : VoiceOutputState()
    data object Initializing : VoiceOutputState()
    data class Speaking(val utteranceId: String, val text: String) : VoiceOutputState()
    data class Error(val message: String) : VoiceOutputState()
}

/**
 * Natural spoken response synthesizer using Android's TextToSpeech API.
 * Cleans markdown and technical formatting, manages audio focus, splits long passages,
 * and allows immediate user interruption.
 */
class VoiceOutputManager(
    private val context: Context,
    private val onComplete: () -> Unit = {},
    private val onError: (String) -> Unit = {}
) : TextToSpeech.OnInitListener {

    companion object {
        private const val TAG = "VoiceOutputManager"
        private const val MAX_UTTERANCE_CHARS = 350
    }

    private var tts: TextToSpeech? = null
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
    private var focusRequest: AudioFocusRequest? = null

    @Volatile
    private var isInitialized = false

    private val _state = MutableStateFlow<VoiceOutputState>(VoiceOutputState.Initializing)
    val state: StateFlow<VoiceOutputState> = _state.asStateFlow()

    init {
        try {
            tts = TextToSpeech(context.applicationContext, this)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to instantiate TextToSpeech: ${e.message}")
            _state.value = VoiceOutputState.Error("TTS initialization failed: ${e.message}")
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            isInitialized = true
            _state.value = VoiceOutputState.Idle
            Log.i(TAG, "TextToSpeech successfully initialized.")

            tts?.language = Locale.getDefault()
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    Log.d(TAG, "TTS started utterance: $utteranceId")
                }

                override fun onDone(utteranceId: String?) {
                    Log.d(TAG, "TTS finished utterance: $utteranceId")
                    abandonAudioFocus()
                    _state.value = VoiceOutputState.Idle
                    onComplete()
                }

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    Log.w(TAG, "TTS failed on utterance: $utteranceId")
                    abandonAudioFocus()
                    _state.value = VoiceOutputState.Idle
                    onError("Speech synthesis encountered an error.")
                }

                override fun onError(utteranceId: String?, errorCode: Int) {
                    Log.w(TAG, "TTS failed on utterance: $utteranceId with code $errorCode")
                    abandonAudioFocus()
                    _state.value = VoiceOutputState.Idle
                    onError("Speech synthesis failed ($errorCode).")
                }
            })
        } else {
            isInitialized = false
            _state.value = VoiceOutputState.Error("TextToSpeech engine failed to initialize (status $status)")
            Log.e(TAG, "TextToSpeech initialization returned status $status")
            onError("TextToSpeech unavailable.")
        }
    }

    /**
     * Cleans markdown, formatting artifacts, and raw technical symbols so speech sounds human.
     */
    fun cleanTextForSpeech(raw: String): String {
        var text = raw.trim()

        // 1. Remove code blocks ```...```
        text = text.replace(Regex("```[\\s\\S]*?```"), "Code block omitted.")

        // 2. Remove inline code `...`
        text = text.replace(Regex("`([^`]+)`"), "$1")

        // 3. Remove Markdown bold/italic **text**, *text*, __text__
        text = text.replace(Regex("[*_]{1,3}(.*?)[*_]{1,3}"), "$1")

        // 4. Remove Markdown links [Label](url) -> Label
        text = text.replace(Regex("\\[([^\\]]+)\\]\\([^)]+\\)"), "$1")

        // 5. Remove raw URLs
        text = text.replace(Regex("https?://\\S+"), "link")

        // 6. Clean bullets (- or * at start of lines)
        text = text.replace(Regex("(?m)^\\s*[-*•]\\s+"), "")

        // 7. Remove JSON structural markers
        text = text.replace(Regex("[{}\\[\\]\"]"), "")

        // 8. Collapse whitespace
        text = text.replace(Regex("\\s+"), " ").trim()

        return text
    }

    /**
     * Speaks the assistant response text aloud, managing focus, sentence chunking, and interruptions.
     */
    fun speak(rawText: String, queueMode: Int = TextToSpeech.QUEUE_FLUSH): Boolean {
        if (!isInitialized || tts == null) {
            Log.w(TAG, "Cannot speak: TextToSpeech is not ready.")
            return false
        }

        val speechText = cleanTextForSpeech(rawText)
        if (speechText.isBlank()) return false

        requestAudioFocus()

        val chunks = splitIntoChunks(speechText, MAX_UTTERANCE_CHARS)
        val batchId = UUID.randomUUID().toString()

        _state.value = VoiceOutputState.Speaking(batchId, speechText)

        for (i in chunks.indices) {
            val chunk = chunks[i]
            val mode = if (i == 0) queueMode else TextToSpeech.QUEUE_ADD
            val utteranceId = "$batchId-$i"

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                val params = Bundle().apply {
                    putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, 1.0f)
                }
                tts?.speak(chunk, mode, params, utteranceId)
            } else {
                @Suppress("DEPRECATION")
                tts?.speak(chunk, mode, null)
            }
        }
        return true
    }

    fun stop() {
        try {
            tts?.stop()
        } catch (e: Exception) {
            Log.w(TAG, "Error stopping TTS: ${e.message}")
        } finally {
            abandonAudioFocus()
            _state.value = VoiceOutputState.Idle
        }
    }

    fun setSpeechRate(rate: Float) {
        tts?.setSpeechRate(rate.coerceIn(0.5f, 2.0f))
    }

    fun setPitch(pitch: Float) {
        tts?.setPitch(pitch.coerceIn(0.5f, 2.0f))
    }

    private fun splitIntoChunks(text: String, maxLen: Int): List<String> {
        if (text.length <= maxLen) return listOf(text)

        val sentences = text.split(Regex("(?<=[.!?])\\s+"))
        val result = mutableListOf<String>()
        var current = StringBuilder()

        for (s in sentences) {
            if (current.length + s.length + 1 > maxLen) {
                if (current.isNotBlank()) {
                    result.add(current.toString().trim())
                    current = StringBuilder()
                }
            }
            if (s.length > maxLen) {
                // Hard split for very long single sentences
                var remaining = s
                while (remaining.length > maxLen) {
                    result.add(remaining.take(maxLen))
                    remaining = remaining.drop(maxLen)
                }
                current.append(remaining).append(" ")
            } else {
                current.append(s).append(" ")
            }
        }
        if (current.isNotBlank()) {
            result.add(current.toString().trim())
        }
        return result
    }

    private fun requestAudioFocus() {
        val am = audioManager ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANT)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .build()
            focusRequest = req
            am.requestAudioFocus(req)
        } else {
            @Suppress("DEPRECATION")
            am.requestAudioFocus(null, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
        }
    }

    private fun abandonAudioFocus() {
        val am = audioManager ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            focusRequest?.let { am.abandonAudioFocusRequest(it) }
            focusRequest = null
        } else {
            @Suppress("DEPRECATION")
            am.abandonAudioFocus(null)
        }
    }

    fun shutdown() {
        stop()
        tts?.shutdown()
        tts = null
        isInitialized = false
    }
}
