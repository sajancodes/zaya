package com.zaya.companion

import com.zaya.companion.audio.PcmQueue
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Voice must never become a memory leak.
 *
 * The original bug was counting frames instead of bytes: a "small" 100-frame
 * queue is four seconds of stale speech. These tests pin the byte budget and the
 * drop-oldest rule, which is what keeps a slow phone from lagging behind reality.
 */
class PcmQueueTest {

    @Test
    fun `queued bytes are counted, not frames`() {
        val queue = PcmQueue(maxBytes = 100)
        queue.offer(ByteArray(40))
        queue.offer(ByteArray(40))

        assertEquals(80, queue.bytes)
        assertEquals(2, queue.size)
    }

    @Test
    fun `over budget drops the oldest audio and keeps the newest`() {
        val queue = PcmQueue(maxBytes = 100)
        val oldest = ByteArray(40) { 1 }
        val middle = ByteArray(40) { 2 }
        val newest = ByteArray(40) { 3 }
        queue.offer(oldest)
        queue.offer(middle)

        queue.offer(newest)

        assertEquals(80, queue.bytes)
        assertEquals(1L, queue.dropped)
        assertEquals(2, queue.poll()!![0].toInt())
        assertEquals(3, queue.poll()!![0].toInt())
        assertNull(queue.poll())
    }

    @Test
    fun `a frame bigger than the whole budget is refused and counted`() {
        val queue = PcmQueue(maxBytes = 64)
        queue.offer(ByteArray(32))

        queue.offer(ByteArray(500))

        assertEquals(32, queue.bytes)
        assertEquals(1L, queue.dropped)
        assertNotNull(queue.poll())
    }

    @Test
    fun `clear empties without pretending anything was dropped`() {
        val queue = PcmQueue(maxBytes = 100)
        queue.offer(ByteArray(50))
        queue.clear()

        assertEquals(0, queue.bytes)
        assertEquals(0, queue.size)
        assertNull(queue.poll())
    }

    @Test
    fun `an empty frame is ignored`() {
        val queue = PcmQueue(maxBytes = 100)
        queue.offer(ByteArray(0))
        assertEquals(0, queue.bytes)
        assertEquals(0L, queue.dropped)
    }

    @Test
    fun `the default budget is about two seconds of Zaya's voice`() {
        // 24 kHz, 16-bit, mono → 48 000 bytes per second.
        val bytes = PcmQueue.DEFAULT_MAX_BYTES
        val seconds = bytes.toDouble() / (24_000.0 * 2.0)
        assertEquals(2.0, seconds, 0.1)
    }
}
