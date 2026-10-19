package com.zaya.companion

import com.zaya.companion.core.CommandTracker
import com.zaya.companion.protocol.Protocol
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * A double tap on Send must not run the command twice.
 *
 * The laptop refuses the same request id twice, so the phone's job is to not
 * invent a second id for the same intent — including after a reconnect, when the
 * same text is legitimately sent again.
 */
class CommandTrackerTest {

    private class FakeClock {
        var now: Long = 1_000L
        fun read(): Long = now
        fun advance(millis: Long) {
            now += millis
        }
    }

    @Test
    fun `the same text within the window reuses the request id`() {
        val clock = FakeClock()
        val tracker = CommandTracker(clock = clock::read)

        val first = tracker.requestIdFor("summarise my inbox")
        val second = tracker.requestIdFor("summarise my inbox")

        assertEquals(first, second)
    }

    @Test
    fun `different text is a different command`() {
        val tracker = CommandTracker(clock = { 1_000L })
        assertNotEquals(tracker.requestIdFor("one"), tracker.requestIdFor("two"))
    }

    @Test
    fun `once the laptop answers, the same text is a new intent`() {
        val tracker = CommandTracker(clock = { 1_000L })
        val first = tracker.requestIdFor("open the report")
        tracker.update(first, Protocol.STATUS_COMPLETED)

        val second = tracker.requestIdFor("open the report")

        assertNotEquals(first, second)
    }

    @Test
    fun `a failed command does not swallow the retry`() {
        val tracker = CommandTracker(clock = { 1_000L })
        val first = tracker.requestIdFor("try again")
        tracker.update(first, Protocol.STATUS_FAILED)

        assertNotEquals(first, tracker.requestIdFor("try again"))
    }

    @Test
    fun `outside the dedupe window nothing is folded`() {
        val clock = FakeClock()
        val tracker = CommandTracker(clock = clock::read)
        val first = tracker.requestIdFor("what is on my screen")

        clock.advance(Protocol.DEDUPE_WINDOW_MILLIS + 1)

        assertNotEquals(first, tracker.requestIdFor("what is on my screen"))
    }

    @Test
    fun `in flight is what a reconnect resends`() {
        val tracker = CommandTracker(clock = { 1_000L })
        val pending = tracker.requestIdFor("first")
        val done = tracker.requestIdFor("second")
        tracker.update(done, Protocol.STATUS_COMPLETED)

        val inFlight = tracker.inFlight().map { it.first }

        assertTrue(inFlight.contains(pending))
        assertFalse(inFlight.contains(done))
    }

    @Test
    fun `history stays bounded`() {
        val tracker = CommandTracker(clock = { 1_000L }, historyLimit = 5)
        val ids = (1..10).map { tracker.requestIdFor("command $it") }

        assertFalse(tracker.isKnown(ids.first()))
        assertTrue(tracker.isKnown(ids.last()))
        assertEquals(5, ids.count { tracker.isKnown(it) })
    }

    @Test
    fun `forgetting a command drops it`() {
        val tracker = CommandTracker(clock = { 1_000L })
        val id = tracker.requestIdFor("gone")
        tracker.forget(id)
        assertFalse(tracker.isKnown(id))
    }
}
