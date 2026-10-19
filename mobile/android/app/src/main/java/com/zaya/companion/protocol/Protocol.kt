package com.zaya.companion.protocol

import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/**
 * The wire contract with the laptop runtime.
 *
 * This mirrors `core/mobile_protocol.py` and is deliberately the only place that
 * knows the wire shape. Every value on screen comes from the laptop: the phone
 * never decides what Zaya feels or what state she is in, it only renders what
 * arrives here.
 *
 * Envelope: `{protocol_version, type, timestamp, payload}` — `payload` is always
 * an object, unknown `type`s are ignored, which is what lets the laptop add
 * events without shipping a new APK.
 */
object Protocol {
    const val VERSION = 1

    /** Zaya's own voice comes back at this rate; the phone microphone goes up at the other. */
    const val DOWNLINK_RATE = 24_000
    const val UPLINK_RATE = 16_000
    const val CHANNELS = 1
    const val BIT_DEPTH_BYTES = 2

    /** The largest binary frame the laptop will accept from the phone microphone. */
    const val MAX_FRAME_BYTES = 32_768

    // Bounds from the laptop's LIMITS map: applied again here so a hostile or
    // buggy frame can never grow the phone's memory.
    const val MAX_TEXT = 4_000
    const val MAX_CAPTION = 600
    const val MAX_TITLE = 160
    const val MAX_DETAIL = 1_200
    const val MAX_REFERENCE = 200
    const val MAX_CHAT_LINES = 300
    const val MAX_TASK_ROWS = 60
    const val MAX_NOTIFICATIONS = 100

    // ── visual states (the laptop is the only authority) ──────────────────────
    const val STANDBY = "STANDBY"
    const val LISTENING = "LISTENING"
    const val THINKING = "THINKING"
    const val SPEAKING = "SPEAKING"
    const val SLEEPING = "SLEEPING"
    const val TASK_RUNNING = "TASK_RUNNING"
    const val ERROR = "ERROR"
    const val MUTED = "MUTED"
    const val CONNECTING = "CONNECTING"

    val STATES = setOf(
        STANDBY, LISTENING, THINKING, SPEAKING, SLEEPING,
        TASK_RUNNING, ERROR, MUTED, CONNECTING,
    )

    val EMOTIONS = setOf("neutral", "happy", "sad", "angry", "surprised")

    // ── call priorities ──────────────────────────────────────────────────────
    const val P0_CRITICAL = 0
    const val P1_IMMEDIATE = 1
    const val P2_IMPORTANT = 2
    const val P3_NORMAL = 3

    /** Only these may ring the phone; P2 is a notification and P3 stays quiet. */
    fun ringsOnPhone(priority: Int): Boolean = priority <= P1_IMMEDIATE
    fun notifiesPhone(priority: Int): Boolean = priority <= P2_IMPORTANT

    // ── message types ────────────────────────────────────────────────────────
    object Type {
        const val HELLO = "hello"
        const val PONG = "pong"
        const val ERROR = "error"

        const val STATE = "zaya.state"
        const val CAPTION = "zaya.caption"
        const val CHAT = "chat.message"
        const val COMMAND_STATUS = "command.status"

        const val TASK_CREATED = "task.created"
        const val TASK_UPDATED = "task.updated"
        const val TASK_COMPLETED = "task.completed"
        const val TASK_FAILED = "task.failed"
        const val TASK_CANCELLED = "task.cancelled"

        const val WHATSAPP_MESSAGE = "whatsapp.message.received"
        const val WHATSAPP_ALERT = "whatsapp.alert.created"
        const val WHATSAPP_MODE = "whatsapp.mode"

        const val WARNING = "system.warning"
        const val NOTIFY = "system.notify"
        const val NOTIFICATION = "notification"

        const val CALL_INCOMING = "call.incoming"
        const val CALL_DIALING = "call.dialing"
        const val CALL_ANSWERED = "call.answered"
        const val CALL_ENDED = "call.ended"
        const val CALL_MISSED = "call.missed"
        const val CALL_MUTE = "system.call.mute"
        const val CALL_VIDEO = "system.call.video"

        // IRIS-MX Mobile Extensions
        const val CALL_CONTROL = "mobile.call_control"
        const val NOTIFICATION_LISTENER = "mobile.notification_listener"
        const val HARDWARE_ACTION = "mobile.hardware_action"
        const val CALL_ANNOUNCE = "mobile.call_announce"
        const val AUTO_REPLY = "mobile.auto_reply"
        const val DEVICE_STATUS = "mobile.device_status"
        const val DOUBLE_CLAP_CONFIG = "mobile.double_clap_config"
        const val MEDIA_CONTROL = "mobile.media_control"
        const val OPEN_DEEP_LINK = "mobile.deep_link"
        const val LAUNCH_APP = "mobile.launch_app"
    }

    // ── uplink control messages (phone → laptop) ─────────────────────────────
    object Control {
        const val PING = "ping"
        const val HELLO = "hello"
        const val COMMAND = "command"
        const val OUTPUT = "output.target"
        const val CALL_ANSWER = "call.answer"
        const val CALL_DECLINE = "call.decline"
        const val CALL_END = "call.end"
        const val CALL_START = "call.start"
        const val CALL_MUTE = "call.mute"
        const val WHATSAPP_MODE = "whatsapp.mode"

        // IRIS-MX Mobile Uplinks
        const val NOTIFICATION_EVENT = "notification.event"
        const val HARDWARE_STATUS = "hardware.status"
        const val DOUBLE_CLAP_DETECTED = "double_clap.detected"
        const val ACTION_RESULT = "action.result"
    }

    // ── command lifecycle (mirrors core/remote_commands.py) ──────────────────
    const val STATUS_SUBMITTED = "submitted"
    const val STATUS_ACKNOWLEDGED = "acknowledged"
    const val STATUS_EXECUTING = "executing"
    const val STATUS_COMPLETED = "completed"
    const val STATUS_FAILED = "failed"
    const val DEDUPE_WINDOW_MILLIS = 2_500L

    object Output {
        const val DESKTOP = "desktop"
        const val PHONE = "phone"
        const val BOTH = "both"
        val TARGETS = setOf(DESKTOP, PHONE, BOTH)
    }

    object WhatsappMode {
        const val GLOBAL_AUTO = "auto"
        const val GLOBAL_OBSERVE = "observe"
        val GLOBAL = listOf(GLOBAL_AUTO, GLOBAL_OBSERVE)
        val PER_CHAT = listOf("observe", "draft", "auto", "manual", "paused")
    }

    /** Public states only; anything else collapses exactly like the laptop collapses it. */
    fun normalizeState(raw: String?): String {
        val name = (raw ?: "").trim().uppercase().replace('-', '_').replace(' ', '_')
        if (name.isEmpty()) return STANDBY
        if (name in STATES) return name
        if (name.startsWith("TASK")) return TASK_RUNNING
        return when (name) {
            "IDLE", "READY" -> STANDBY
            "WAITING" -> LISTENING
            "OFFLINE", "DISCONNECTED" -> ERROR
            else -> STANDBY
        }
    }

    fun normalizeEmotion(raw: String?, default: String = "neutral"): String {
        val name = (raw ?: "").trim().lowercase()
        return if (name in EMOTIONS) name else default
    }

    /** Bounded, control-character-free text — the same sanitising the laptop does. */
    fun clip(value: String?, limit: Int, default: String = ""): String {
        if (value == null) return default
        val cleaned = buildString(value.length) {
            for (ch in value) {
                if (ch == '\n' || ch == '\t' || ch.code >= 32) append(ch)
            }
        }.trim()
        return if (cleaned.length <= limit) cleaned else cleaned.substring(0, limit)
    }

    fun newRequestId(): String = UUID.randomUUID().toString().replace("-", "").take(32)
}

/** Parsed envelope. `payload` is always present, possibly empty. */
data class Envelope(
    val type: String,
    val payload: JSONObject,
    val timestamp: Double,
    val version: Int,
) {
    companion object {
        /**
         * Parse whatever arrived on the socket. Junk, a bare string or a payload
         * of the wrong shape all come back as null instead of throwing: a remote
         * message must never be able to crash the phone.
         */
        fun parse(text: String?): Envelope? {
            if (text.isNullOrBlank()) return null
            return try {
                val raw = JSONObject(text)
                val type = raw.optString("type", "").trim()
                if (type.isEmpty()) return null
                val payload = raw.optJSONObject("payload") ?: JSONObject()
                Envelope(
                    type = type,
                    payload = payload,
                    timestamp = raw.optDouble("timestamp", 0.0),
                    version = raw.optInt("protocol_version", Protocol.VERSION),
                )
            } catch (_: Exception) {
                null
            }
        }
    }
}

/** Small, total readers: a missing key is never an exception on this side. */
internal fun JSONObject.str(key: String, limit: Int = Protocol.MAX_DETAIL): String =
    Protocol.clip(if (isNull(key)) "" else optString(key, ""), limit)

internal fun JSONObject.num(key: String, fallback: Double = 0.0): Double =
    if (has(key) && !isNull(key)) optDouble(key, fallback) else fallback

internal fun JSONObject.flag(key: String, fallback: Boolean = false): Boolean =
    if (has(key) && !isNull(key)) optBoolean(key, fallback) else fallback

internal fun JSONObject.child(key: String): JSONObject? = optJSONObject(key)

internal fun JSONObject.array(key: String): JSONArray? = optJSONArray(key)
