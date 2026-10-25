package com.zaya.companion.core

import com.zaya.companion.protocol.Protocol

/**
 * The phone's half of the duplicate-command guard.
 *
 * The laptop already refuses to run the same request id twice, and it also
 * folds two identical commands sent within [Protocol.DEDUPE_WINDOW_MILLIS] into
 * one. That only helps if the phone stops minting fresh ids for the same tap:
 * a double-tap on Send, or a retry after a flaky socket, must reuse the id so
 * the laptop recognises it as the same request instead of running it twice.
 */
class CommandTracker(
    private val clock: () -> Long = System::currentTimeMillis,
    private val historyLimit: Int = 200,
    private val dedupeWindowMillis: Long = Protocol.DEDUPE_WINDOW_MILLIS,
) {
    private data class Entry(
        val requestId: String,
        val text: String,
        val at: Long,
        var status: String,
    )

    private val entries = LinkedHashMap<String, Entry>()

    /** Request id to send for [text]: an in-flight twin's id, or a fresh one. */
    @Synchronized
    fun requestIdFor(text: String): String {
        val now = clock()
        prune(now)
        val twin = entries.values.lastOrNull { entry ->
            entry.text == text &&
                !entry.status.let { it == Protocol.STATUS_COMPLETED || it == Protocol.STATUS_FAILED } &&
                now - entry.at <= dedupeWindowMillis
        }
        if (twin != null) return twin.requestId
        val requestId = Protocol.newRequestId()
        entries[requestId] = Entry(requestId, text, now, Protocol.STATUS_SUBMITTED)
        trim()
        return requestId
    }

    /** Record a command the phone decided to send later (offline outbox). */
    @Synchronized
    fun record(requestId: String, text: String, status: String = Protocol.STATUS_SUBMITTED) {
        entries[requestId] = Entry(requestId, text, clock(), status)
        trim()
    }

    @Synchronized
    fun update(requestId: String, status: String) {
        entries[requestId]?.status = status
    }

    @Synchronized
    fun status(requestId: String): String? = entries[requestId]?.status

    @Synchronized
    fun isKnown(requestId: String): Boolean = entries.containsKey(requestId)

    /** Ids still waiting for a terminal answer; resent after a reconnect. */
    @Synchronized
    fun inFlight(): List<Pair<String, String>> {
        prune(clock())
        return entries.values.filter { it.status != Protocol.STATUS_COMPLETED && it.status != Protocol.STATUS_FAILED }
            .map { it.requestId to it.text }
    }

    @Synchronized
    fun forget(requestId: String) {
        entries.remove(requestId)
    }

    /** Keeps the map bounded; terminal and stale entries fall out oldest-first. */
    private fun prune(now: Long) {
        val iterator = entries.entries.iterator()
        while (iterator.hasNext()) {
            val entry = iterator.next().value
            val age = now - entry.at
            val terminal = entry.status == Protocol.STATUS_COMPLETED ||
                entry.status == Protocol.STATUS_FAILED
            if (terminal && age > dedupeWindowMillis) iterator.remove()
            else if (age > DEDUPE_MEMORY_MILLIS) iterator.remove()
        }
    }

    private fun trim() {
        while (entries.size > historyLimit) {
            val oldest = entries.keys.firstOrNull() ?: return
            entries.remove(oldest)
        }
    }

    private companion object {
        const val DEDUPE_MEMORY_MILLIS = 10 * 60 * 1000L
    }
}
