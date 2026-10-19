package com.zaya.companion.core

import kotlin.math.min
import kotlin.random.Random

/**
 * Reconnect pacing: start fast, back off to a ceiling, and keep a little jitter
 * so a phone that wakes up with no signal does not hammer the laptop forever.
 */
class Backoff(
    private val baseMillis: Long = 1_000L,
    private val maxMillis: Long = 30_000L,
    private val factor: Double = 2.0,
    private val jitter: Double = 0.25,
    private val random: Random = Random.Default,
) {
    var attempts: Int = 0
        private set

    /** Delay before the next attempt, and count it. */
    fun nextDelayMillis(): Long {
        val exponent = attempts.coerceAtMost(MAX_EXPONENT)
        val raw = min(maxMillis.toDouble(), baseMillis.toDouble() * Math.pow(factor, exponent.toDouble()))
        attempts += 1
        return applyJitter(raw.toLong())
    }

    /** Called when a connection has proved itself; the next failure starts over. */
    fun reset() {
        attempts = 0
    }

    private fun applyJitter(delay: Long): Long {
        if (jitter <= 0.0) return delay
        val span = (delay * jitter).toLong().coerceAtLeast(1L)
        val offset = random.nextLong(-span, span + 1)
        return (delay + offset).coerceIn(250L, maxMillis + span)
    }

    private companion object {
        const val MAX_EXPONENT = 16
    }
}
