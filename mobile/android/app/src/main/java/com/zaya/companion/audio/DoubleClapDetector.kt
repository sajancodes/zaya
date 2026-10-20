package com.zaya.companion.audio

import kotlin.math.sqrt

/**
 * Real-time acoustic double-clap detector for Android.
 *
 * Processes 16-bit PCM mono audio buffers, detects transient energy spikes
 * exceeding ambient floor, and triggers when two claps occur within 150ms - 700ms.
 */
class DoubleClapDetector(
    var enabled: Boolean = true,
    var energyRatioThreshold: Float = 3.8f,
    var minClapIntervalMs: Long = 150L,
    var maxClapIntervalMs: Long = 700L,
    var onDoubleClap: () -> Unit = {},
) {
    private var ambientFloor: Float = 100.0f
    private var lastClapTimeMs: Long = 0L
    private var clapCount: Int = 0

    fun processFrame(pcmBytes: ByteArray, length: Int) {
        if (!enabled || length < 2) return

        var sumSq = 0.0
        val numSamples = length / 2
        for (i in 0 until numSamples) {
            val sample = (pcmBytes[i * 2].toInt() and 0xFF) or (pcmBytes[i * 2 + 1].toInt() shl 8)
            val sampleShort = sample.toShort()
            sumSq += sampleShort * sampleShort
        }
        val rms = sqrt(sumSq / numSamples).toFloat()

        // Adaptive ambient energy tracking (slow decay)
        if (rms < ambientFloor * 2.0f) {
            ambientFloor = ambientFloor * 0.95f + rms * 0.05f
        }
        if (ambientFloor < 30.0f) ambientFloor = 30.0f

        val now = System.currentTimeMillis()
        val ratio = rms / ambientFloor

        if (ratio >= energyRatioThreshold && rms > 250.0f) {
            // Transient spike detected
            if (clapCount == 0) {
                clapCount = 1
                lastClapTimeMs = now
            } else if (clapCount == 1) {
                val delta = now - lastClapTimeMs
                if (delta in minClapIntervalMs..maxClapIntervalMs) {
                    clapCount = 0
                    lastClapTimeMs = 0L
                    onDoubleClap()
                } else if (delta > maxClapIntervalMs) {
                    // Stale first clap, reset to this as first
                    clapCount = 1
                    lastClapTimeMs = now
                }
            }
        } else if (clapCount == 1 && (now - lastClapTimeMs) > maxClapIntervalMs) {
            clapCount = 0
        }
    }

    fun reset() {
        clapCount = 0
        lastClapTimeMs = 0L
    }
}
