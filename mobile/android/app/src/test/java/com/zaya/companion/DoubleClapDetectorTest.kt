package com.zaya.companion

import com.zaya.companion.audio.DoubleClapDetector
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DoubleClapDetectorTest {

    private fun makeSilenceFrame(): ByteArray {
        return ByteArray(1024) { 0 }
    }

    private fun makeClapFrame(): ByteArray {
        val bytes = ByteArray(1024)
        for (i in 0 until 512) {
            val v: Short = 15000
            bytes[i * 2] = (v.toInt() and 0xFF).toByte()
            bytes[i * 2 + 1] = ((v.toInt() shr 8) and 0xFF).toByte()
        }
        return bytes
    }

    @Test
    fun `silence does not trigger clap`() {
        var triggered = false
        val detector = DoubleClapDetector(onDoubleClap = { triggered = true })
        val silence = makeSilenceFrame()
        for (i in 0 until 10) {
            detector.processFrame(silence, silence.size)
        }
        assertFalse(triggered)
    }

    @Test
    fun `two claps within interval trigger double clap callback`() {
        var count = 0
        val detector = DoubleClapDetector(
            minClapIntervalMs = 10L,
            maxClapIntervalMs = 500L,
            onDoubleClap = { count++ },
        )

        val silence = makeSilenceFrame()
        val clap = makeClapFrame()

        // Calibrate ambient
        for (i in 0 until 5) {
            detector.processFrame(silence, silence.size)
        }

        // First clap
        detector.processFrame(clap, clap.size)
        Thread.sleep(50)

        // Second clap
        detector.processFrame(clap, clap.size)

        assertEquals(1, count)
    }
}
