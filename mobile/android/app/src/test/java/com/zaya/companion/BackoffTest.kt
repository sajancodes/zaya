package com.zaya.companion

import com.zaya.companion.core.Backoff
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.random.Random

class BackoffTest {

    @Test
    fun `delays double then stop at the ceiling`() {
        val backoff = Backoff(
            baseMillis = 100L,
            maxMillis = 800L,
            factor = 2.0,
            jitter = 0.0,
        )

        assertEquals(100L, backoff.nextDelayMillis())
        assertEquals(200L, backoff.nextDelayMillis())
        assertEquals(400L, backoff.nextDelayMillis())
        assertEquals(800L, backoff.nextDelayMillis())
        assertEquals(800L, backoff.nextDelayMillis())
        assertEquals(5, backoff.attempts)
    }

    @Test
    fun `a healthy connection starts the curve over`() {
        val backoff = Backoff(baseMillis = 100L, maxMillis = 800L, jitter = 0.0)
        repeat(4) { backoff.nextDelayMillis() }

        backoff.reset()

        assertEquals(0, backoff.attempts)
        assertEquals(100L, backoff.nextDelayMillis())
    }

    @Test
    fun `jitter spreads retries without inventing silly delays`() {
        val backoff = Backoff(
            baseMillis = 1_000L,
            maxMillis = 1_000L,
            factor = 2.0,
            jitter = 0.25,
            random = Random(7),
        )

        repeat(20) {
            val delay = backoff.nextDelayMillis()
            assertTrue("delay was $delay", delay in 250L..1_251L)
        }
    }

    @Test
    fun `a fresh tracker has not failed yet`() {
        assertEquals(0, Backoff().attempts)
    }
}
