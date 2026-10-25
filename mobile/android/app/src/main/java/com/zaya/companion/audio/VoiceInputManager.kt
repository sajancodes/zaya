package com.zaya.companion.audio

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale

sealed class VoiceInputState {
    data object Idle : VoiceInputState()
    data object Listening : VoiceInputState()
    data object Processing : VoiceInputState()
    data class Success(val recognizedText: String) : VoiceInputState()
    data class Error(val message: String, val canRetry: Boolean = true) : VoiceInputState()
}

/**
 * Transparent, user-initiated Speech-to-Text coordinator using Android's SpeechRecognizer API.
 * Never records in the background without explicit user activation.
 */
class VoiceInputManager(
    private val context: Context,
    private val onResult: (String) -> Unit = {},
    private val onError: (String) -> Unit = {}
) {
    companion object {
        private const val TAG = "VoiceInputManager"
        private const val MAX_SPEECH_DURATION_MS = 10_000L
    }

    private val mainHandler = Handler(Looper.getMainLooper())
    private var recognizer: SpeechRecognizer? = null

    private val _state = MutableStateFlow<VoiceInputState>(VoiceInputState.Idle)
    val state: StateFlow<VoiceInputState> = _state.asStateFlow()

    private val recognitionListener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) {
            Log.d(TAG, "SpeechRecognizer ready for user speech.")
            _state.value = VoiceInputState.Listening
        }

        override fun onBeginningOfSpeech() {
            Log.d(TAG, "User began speaking.")
            _state.value = VoiceInputState.Listening
        }

        override fun onRmsChanged(rmsdB: Float) {}

        override fun onBufferReceived(buffer: ByteArray?) {}

        override fun onEndOfSpeech() {
            Log.d(TAG, "Speech ended. Processing audio.")
            _state.value = VoiceInputState.Processing
        }

        override fun onError(errorCode: Int) {
            val (msg, canRetry) = when (errorCode) {
                SpeechRecognizer.ERROR_AUDIO -> "Audio recording error" to true
                SpeechRecognizer.ERROR_CLIENT -> "Speech recognition client error" to true
                SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission required" to false
                SpeechRecognizer.ERROR_NETWORK -> "Network connection error during recognition" to true
                SpeechRecognizer.ERROR_NETWORK_TIMEOUT -> "Network timed out" to true
                SpeechRecognizer.ERROR_NO_MATCH -> "No speech recognized. Please try speaking again." to true
                SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "Speech recognizer is busy" to true
                SpeechRecognizer.ERROR_SERVER -> "Recognition server error" to true
                SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "No speech detected" to true
                else -> "Speech recognition error ($errorCode)" to true
            }
            Log.w(TAG, "Speech recognition error: $msg ($errorCode)")
            _state.value = VoiceInputState.Error(msg, canRetry)
            onError(msg)
            cleanup()
        }

        override fun onResults(results: Bundle?) {
            val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val topMatch = matches?.firstOrNull()?.trim()

            if (!topMatch.isNullOrBlank()) {
                Log.i(TAG, "Recognized speech: \"$topMatch\"")
                _state.value = VoiceInputState.Success(topMatch)
                onResult(topMatch)
            } else {
                _state.value = VoiceInputState.Error("No readable speech recognized.", canRetry = true)
                onError("No readable speech recognized.")
            }
            cleanup()
        }

        override fun onPartialResults(partialResults: Bundle?) {
            val partialMatches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
            val partial = partialMatches?.firstOrNull()?.trim()
            if (!partial.isNullOrBlank()) {
                _state.value = VoiceInputState.Success(partial)
            }
        }

        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    fun hasMicrophonePermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * Starts listening on the Android main thread with timeout bounds and error handling.
     */
    fun startListening(languageLocale: Locale = Locale.getDefault()): Boolean {
        if (!hasMicrophonePermission()) {
            _state.value = VoiceInputState.Error("Microphone permission is required.", canRetry = false)
            onError("Microphone permission is required.")
            return false
        }

        if (!SpeechRecognizer.isRecognitionAvailable(context)) {
            _state.value = VoiceInputState.Error("Speech recognition is not available on this device.", canRetry = false)
            onError("Speech recognition is not available on this device.")
            return false
        }

        mainHandler.post {
            try {
                cleanup()

                val activeRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
                activeRecognizer.setRecognitionListener(recognitionListener)
                recognizer = activeRecognizer

                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageLocale.toLanguageTag())
                    putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                    putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
                    putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1500L)
                    putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1000L)
                }

                _state.value = VoiceInputState.Listening
                activeRecognizer.startListening(intent)

                // Safety timeout to avoid indefinite recording
                mainHandler.postDelayed({
                    if (_state.value is VoiceInputState.Listening) {
                        stopListening()
                    }
                }, MAX_SPEECH_DURATION_MS)

            } catch (e: Exception) {
                Log.e(TAG, "Failed to start speech recognition: ${e.message}")
                _state.value = VoiceInputState.Error("Failed to initialize speech recognition: ${e.message}")
                onError(e.message ?: "Recognition failed")
                cleanup()
            }
        }
        return true
    }

    fun stopListening() {
        mainHandler.post {
            try {
                recognizer?.stopListening()
                _state.value = VoiceInputState.Processing
            } catch (e: Exception) {
                Log.w(TAG, "Error stopping recognizer: ${e.message}")
                cleanup()
            }
        }
    }

    fun cancel() {
        mainHandler.post {
            try {
                recognizer?.cancel()
            } catch (e: Exception) {
                Log.w(TAG, "Error cancelling recognizer: ${e.message}")
            } finally {
                cleanup()
                _state.value = VoiceInputState.Idle
            }
        }
    }

    fun cleanup() {
        mainHandler.post {
            try {
                recognizer?.destroy()
            } catch (e: Exception) {
                Log.w(TAG, "Error destroying recognizer: ${e.message}")
            } finally {
                recognizer = null
                if (_state.value is VoiceInputState.Listening || _state.value is VoiceInputState.Processing) {
                    _state.value = VoiceInputState.Idle
                }
            }
        }
    }
}
