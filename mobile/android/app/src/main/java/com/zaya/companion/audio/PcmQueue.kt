package com.zaya.companion.audio

/**
 * Bounded PCM buffer with a byte budget.
 *
 * Both directions of the voice link go through one of these. Counting frames was
 * the original bug: a 1024-sample frame at 24 kHz is 43 ms, so a 100-frame queue
 * looked harmless and was a four-second tail of stale speech. Bytes are the only
 * honest unit, and when the budget is blown the *oldest* audio is dropped — late
 * speech is intelligible, a stale backlog is not.
 */
class PcmQueue(
    private val maxBytes: Int = DEFAULT_MAX_BYTES,
) {
    private val frames = ArrayDeque<ByteArray>()
    private var queuedBytes = 0

    /** Frames discarded because the consumer fell behind. */
    var dropped: Long = 0L
        private set

    val bytes: Int
        @Synchronized get() = queuedBytes

    val size: Int
        @Synchronized get() = frames.size

    @Synchronized
    fun offer(frame: ByteArray) {
        if (frame.isEmpty()) return
        if (frame.size >= maxBytes) {
            // A single frame bigger than the whole budget can never be played
            // without starving everything after it.
            dropped += 1
            return
        }
        frames.addLast(frame)
        queuedBytes += frame.size
        while (queuedBytes > maxBytes && frames.isNotEmpty()) {
            queuedBytes -= frames.removeFirst().size
            dropped += 1
        }
    }

    @Synchronized
    fun poll(): ByteArray? {
        val frame = frames.removeFirstOrNull() ?: return null
        queuedBytes -= frame.size
        return frame
    }

    @Synchronized
    fun clear() {
        frames.clear()
        queuedBytes = 0
    }

    companion object {
        /** ≈2 s of 24 kHz mono PCM16: enough to ride out a Wi-Fi hiccup, not enough to lag. */
        const val DEFAULT_MAX_BYTES = 24_000 * 2 * 2
    }
}
