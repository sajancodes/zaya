package com.zaya.companion.audio

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import android.util.Log
import com.zaya.companion.protocol.Protocol
import kotlin.math.abs
import kotlin.math.max

/**
 * The phone's microphone, in the PCM shape the laptop already understands.
 *
 * `VOICE_COMMUNICATION` instead of `MIC` on purpose: it is the source that asks
 * the device for its echo canceller, which is the only thing standing between
 * this app and Zaya hearing herself through the phone speaker.
 */
class MicCapture(
    private val sampleRate: Int = Protocol.UPLINK_RATE,
    private val onFrame: (ByteArray) -> Unit,
    private val onError: (String) -> Unit = {},
) {
    @Volatile
    private var running = false

    private var recorder: AudioRecord? = null
    private var thread: Thread? = null
    private var echoCanceler: AcousticEchoCanceler? = null
    private var noiseSuppressor: NoiseSuppressor? = null

    val isRunning: Boolean get() = running

    fun start(): Boolean {
        if (running) return true
        val minBuffer = AudioRecord.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuffer <= 0) {
            onError("This phone can't record at $sampleRate Hz")
            return false
        }
        val active = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                sampleRate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                max(minBuffer * 2, FRAME_BYTES * 4),
            )
        } catch (error: Exception) {
            onError(error.message ?: "No microphone available")
            return false
        }
        if (active.state != AudioRecord.STATE_INITIALIZED) {
            active.release()
            onError("The microphone is busy")
            return false
        }
        recorder = active
        attachCleanup(active.audioSessionId)
        running = true
        thread = Thread({ pump(active) }, "zaya-mic").also {
            it.isDaemon = true
            it.start()
        }
        return true
    }

    fun stop() {
        running = false
        thread?.join(500)
        thread = null
        recorder?.let { active ->
            runCatching { if (active.recordingState == AudioRecord.RECORDSTATE_RECORDING) active.stop() }
            runCatching { active.release() }
        }
        recorder = null
        detachCleanup()
    }

    private fun pump(active: AudioRecord) {
        val frame = ByteArray(FRAME_BYTES)
        try {
            active.startRecording()
        } catch (error: Exception) {
            onError(error.message ?: "Recording refused")
            running = false
            return
        }
        while (running) {
            val read = try {
                active.read(frame, 0, frame.size, AudioRecord.READ_BLOCKING)
            } catch (error: Exception) {
                onError(error.message ?: "Recording failed")
                break
            }
            if (read > 0) {
                onFrame(if (read == frame.size) frame.copyOf() else frame.copyOf(read))
            } else if (read < 0) {
                onError("Microphone error $read")
                break
            }
        }
        runCatching { active.stop() }
        running = false
    }

    private fun attachCleanup(sessionId: Int) {
        echoCanceler = runCatching { usable(AcousticEchoCanceler.create(sessionId)) }
            .getOrNull()
            .also { if (it == null) Log.d(TAG, "no echo canceller on this device") }
        noiseSuppressor = runCatching { usable(NoiseSuppressor.create(sessionId)) }.getOrNull()
    }

    private fun <T : android.media.audiofx.AudioEffect> usable(effect: T?): T? {
        if (effect == null) return null
        effect.enabled = true
        if (!effect.hasControl()) {
            effect.release()
            return null
        }
        return effect
    }

    private fun detachCleanup() {
        runCatching { echoCanceler?.release() }
        runCatching { noiseSuppressor?.release() }
        echoCanceler = null
        noiseSuppressor = null
    }

    companion object {
        private const val TAG = "ZayaMic"

        /** 1024 samples (64 ms at 16 kHz): one Gemini-sized chunk, well inside the frame cap. */
        const val FRAME_BYTES = 1024 * Protocol.BIT_DEPTH_BYTES
    }
}

/**
 * Zaya's voice, out of the phone speaker.
 *
 * Audio arriving from the socket is queued in a bounded byte budget and written
 * to the track by this class's own thread: a slow `write` drops old audio
 * instead of growing memory, and it never blocks the socket reader.
 */
class SpeakerOutput(
    private val communication: Boolean = false,
    private val sampleRate: Int = Protocol.DOWNLINK_RATE,
    private val maxQueuedBytes: Int = PcmQueue.DEFAULT_MAX_BYTES,
    private val onError: (String) -> Unit = {},
) {
    private val queue = PcmQueue(maxQueuedBytes)
    private var track: AudioTrack? = null
    private var thread: Thread? = null

    @Volatile
    private var running = false

    /** Peak level of the last written frame, 0f…1f, for the call UI's meter. */
    @Volatile
    var level: Float = 0f
        private set

    val queuedBytes: Int get() = queue.bytes
    val droppedFrames: Long get() = queue.dropped

    fun start(): Boolean {
        if (running) return true
        val minBuffer = AudioTrack.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuffer <= 0) {
            onError("This phone can't play at $sampleRate Hz")
            return false
        }
        val active = try {
            AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(if (communication) AudioAttributes.USAGE_VOICE_COMMUNICATION else AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build(),
                )
                .setAudioFormat(
                    AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setSampleRate(sampleRate)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build(),
                )
                .setBufferSizeInBytes(max(minBuffer * 2, sampleRate / 2 * Protocol.BIT_DEPTH_BYTES))
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build()
        } catch (error: Exception) {
            onError(error.message ?: "No speaker available")
            return false
        }
        if (active.state != AudioTrack.STATE_INITIALIZED) {
            active.release()
            onError("The speaker is busy")
            return false
        }
        track = active
        running = true
        active.play()
        thread = Thread({ pump(active) }, "zaya-speaker").also {
            it.isDaemon = true
            it.start()
        }
        return true
    }

    fun enqueue(frame: ByteArray) {
        if (frame.isEmpty() || !running) return
        queue.offer(frame)
    }

    fun stop() {
        running = false
        thread?.join(500)
        thread = null
        queue.clear()
        level = 0f
        track?.let { active ->
            runCatching { active.pause() }
            runCatching { active.flush() }
            runCatching { active.stop() }
            runCatching { active.release() }
        }
        track = null
    }

    private fun pump(active: AudioTrack) {
        while (running) {
            val frame = queue.poll()
            if (frame == null) {
                // Nothing to play: let the track drain instead of spinning.
                Thread.sleep(IDLE_SLEEP_MILLIS)
                continue
            }
            level = peak(frame)
            try {
                active.write(frame, 0, frame.size, AudioTrack.WRITE_BLOCKING)
            } catch (error: Exception) {
                onError(error.message ?: "Playback failed")
                break
            }
        }
        level = 0f
        running = false
    }

    private fun peak(frame: ByteArray): Float {
        var loudest = 0
        var index = 0
        while (index + 1 < frame.size) {
            val sample = (frame[index].toInt() and 0xFF) or (frame[index + 1].toInt() shl 8)
            val signed = if (sample > 32767) sample - 65536 else sample
            loudest = max(loudest, abs(signed))
            index += 2
        }
        return (loudest / 32768f).coerceIn(0f, 1f)
    }

    private companion object {
        const val IDLE_SLEEP_MILLIS = 20L
    }
}
