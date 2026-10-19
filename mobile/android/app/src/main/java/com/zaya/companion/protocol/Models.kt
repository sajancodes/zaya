package com.zaya.companion.protocol

import org.json.JSONObject

/** Who a line in the transcript belongs to. */
enum class Speaker { OWNER, ZAYA, NOTICE }

/** One row in the chat/transcript list. */
data class ChatLine(
    val id: String,
    val speaker: Speaker,
    val text: String,
    val at: Long,
    /** Laptop-reported command status for owner lines: submitted…completed/failed. */
    val status: String = "",
    val error: String = "",
    val source: String = "",
) {
    val isTerminal: Boolean
        get() = status == Protocol.STATUS_COMPLETED || status == Protocol.STATUS_FAILED
}

/** What the laptop says Zaya looks like right now. */
data class ZayaVisual(
    val state: String = Protocol.STANDBY,
    val emotion: String = "neutral",
)

data class Caption(val text: String = "", val at: Long = 0L)

/** A task from the laptop's task runtime, projected for a phone screen. */
data class TaskItem(
    val taskId: String,
    val goal: String,
    val state: String,
    val source: String,
    val activeStep: String?,
    val error: String?,
    val attempts: Int,
    val updatedAt: Double,
    val evidenceCount: Int,
    val sideEffectCount: Int,
) {
    val isActive: Boolean
        get() = state.lowercase() !in setOf("completed", "failed", "cancelled")

    companion object {
        fun from(json: JSONObject): TaskItem = TaskItem(
            taskId = json.str("task_id", Protocol.MAX_REFERENCE),
            goal = json.str("goal", Protocol.MAX_TITLE),
            state = json.str("state", 40),
            source = json.str("source", 40),
            activeStep = json.str("active_step", Protocol.MAX_TITLE).ifBlank { null },
            error = json.str("error", Protocol.MAX_DETAIL).ifBlank { null },
            attempts = json.optInt("attempts", 0),
            updatedAt = json.num("updated_at"),
            evidenceCount = json.optInt("evidence_count", 0),
            sideEffectCount = json.optInt("side_effect_count", 0),
        )
    }
}

/** A ringing or running call. The laptop starts it; the phone can answer, decline, end. */
data class CallInfo(
    val callId: String,
    val title: String,
    val detail: String,
    val priority: Int,
    val priorityName: String,
    val reason: String,
    val source: String,
    val state: String,
    val direction: String = "incoming",
    val deviceId: String = "",
) {
    companion object {
        const val STATE_RINGING = "ringing"
        const val STATE_ANSWERED = "answered"
        const val STATE_ENDED = "ended"
        const val STATE_DECLINED = "declined"
        const val STATE_MISSED = "missed"

        fun from(json: JSONObject): CallInfo = CallInfo(
            callId = json.str("call_id", 64),
            title = json.str("title", Protocol.MAX_TITLE),
            detail = json.str("detail", Protocol.MAX_DETAIL),
            priority = json.optInt("priority", Protocol.P2_IMPORTANT),
            priorityName = json.str("priority_name", 20),
            reason = json.str("reason", Protocol.MAX_DETAIL),
            source = json.str("source", 40),
            state = json.str("state", 20),
            direction = json.str("direction", 20).ifBlank { "incoming" },
            deviceId = json.str("device_id", 128),
        )
    }
}

/** State of the phone's side of a call. */
sealed interface CallUiState {
    data object Idle : CallUiState
    data class Dialing(val call: CallInfo) : CallUiState
    data class Ringing(val call: CallInfo) : CallUiState
    data class Active(val call: CallInfo, val answeredAt: Long) : CallUiState
}

/** Something the laptop wants the owner to see. */
data class NotificationItem(
    val key: String,
    val title: String,
    val body: String,
    val priority: Int,
    val priorityName: String,
    val source: String,
    val quiet: Boolean,
    val at: Long,
    val severity: String = "",
    val read: Boolean = false,
)

/** One WhatsApp row as the laptop's read-only view reports it. */
data class WhatsappRow(
    val chatId: String,
    val title: String,
    val summary: String,
    val score: Int = 0,
    val category: String = "",
    val important: Boolean = false,
    val reason: String = "",
)

/** The last WhatsApp answer the laptop gave us. */
data class WhatsappFeed(
    val action: String = "status",
    val status: String = "",
    val summary: String = "",
    val rows: List<WhatsappRow> = emptyList(),
    val evidence: List<String> = emptyList(),
    val globalMode: String = "",
    val aiActive: Boolean = false,
    val feedReady: Boolean = false,
    val chatId: String = "",
    val chatMode: String = "",
    val error: String = "",
)

/** One file in the laptop's uploads folder. */
data class RemoteFile(val name: String, val size: Long, val modified: Double)

enum class ConnectionPhase { UNPAIRED, CONNECTING, ONLINE, OFFLINE, REVOKED, INCOMPATIBLE }

data class ConnectionStatus(
    val phase: ConnectionPhase = ConnectionPhase.UNPAIRED,
    val detail: String = "",
    val retryInSeconds: Int = 0,
    val attempts: Int = 0,
) {
    val isOnline: Boolean get() = phase == ConnectionPhase.ONLINE
}

/** A paired laptop: the address and the device credential that survives restarts. */
data class Pairing(
    val address: String,
    val deviceId: String,
    val secret: String,
    val serverName: String = "Zaya",
    val deviceName: String = "",
) {
    val baseUrl: String get() = normalizeAddress(address)

    companion object {
        /** Accepts `laptop.tailnet.ts.net:8000`, `https://host`, trailing slashes… */
        fun normalizeAddress(raw: String): String {
            var text = raw.trim()
            if (text.isEmpty()) return ""
            if (!text.startsWith("http://") && !text.startsWith("https://")) {
                text = "http://$text"
            }
            return text.trimEnd('/')
        }

        fun wsBase(baseUrl: String): String = when {
            baseUrl.startsWith("https://") -> "wss://" + baseUrl.removePrefix("https://")
            baseUrl.startsWith("http://") -> "ws://" + baseUrl.removePrefix("http://")
            else -> baseUrl
        }

        fun host(baseUrl: String): String = baseUrl
            .removePrefix("https://").removePrefix("http://")
            .substringBefore('/').substringBefore(':')
    }
}
