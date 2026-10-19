package com.zaya.companion.runtime

import com.zaya.companion.core.CommandTracker
import com.zaya.companion.protocol.CallInfo
import com.zaya.companion.protocol.CallUiState
import com.zaya.companion.protocol.Caption
import com.zaya.companion.protocol.ChatLine
import com.zaya.companion.protocol.Envelope
import com.zaya.companion.protocol.NotificationItem
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.protocol.Speaker
import com.zaya.companion.protocol.TaskItem
import com.zaya.companion.protocol.WhatsappFeed
import com.zaya.companion.protocol.WhatsappRow
import com.zaya.companion.protocol.ZayaVisual
import com.zaya.companion.protocol.array
import com.zaya.companion.protocol.child
import com.zaya.companion.protocol.flag
import com.zaya.companion.protocol.num
import com.zaya.companion.protocol.str
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject

/** What the runtime has to do that is not just state on a screen. */
sealed interface RuntimeEffect {
    /** A call worth ringing for (P0/P1) arrived. */
    data class Ring(val call: CallInfo) : RuntimeEffect
    data object StopRinging : RuntimeEffect
    data object Ringback : RuntimeEffect
    data object StartVoice : RuntimeEffect
    data object StopVoice : RuntimeEffect

    /** Something the owner should be told about outside the app. */
    data class Notify(val item: NotificationItem) : RuntimeEffect
}

/** The phone's side of the voice link, for the call UI and the home badge. */
data class VoiceState(
    val micActive: Boolean = false,
    val speakerActive: Boolean = false,
    val muted: Boolean = false,
    val note: String = "",
)

/**
 * Everything the phone believes, in one place.
 *
 * This class is the *only* thing that interprets laptop events, and it does so
 * without touching Android: given the same envelopes it always produces the same
 * screen and the same side effects, which is what makes "the phone never decides
 * anything" checkable in a plain JVM test.
 */
class ZayaModel(
    private val clock: () -> Long = System::currentTimeMillis,
    val tracker: CommandTracker = CommandTracker(clock),
) {
    private val _visual = MutableStateFlow(ZayaVisual())
    val visual: StateFlow<ZayaVisual> = _visual.asStateFlow()

    private val _caption = MutableStateFlow(Caption())
    val caption: StateFlow<Caption> = _caption.asStateFlow()

    private val _chat = MutableStateFlow<List<ChatLine>>(emptyList())
    val chat: StateFlow<List<ChatLine>> = _chat.asStateFlow()

    private val _tasks = MutableStateFlow<List<TaskItem>>(emptyList())
    val tasks: StateFlow<List<TaskItem>> = _tasks.asStateFlow()

    private val _call = MutableStateFlow<CallUiState>(CallUiState.Idle)
    val call: StateFlow<CallUiState> = _call.asStateFlow()

    private val _notifications = MutableStateFlow<List<NotificationItem>>(emptyList())
    val notifications: StateFlow<List<NotificationItem>> = _notifications.asStateFlow()

    private val _whatsapp = MutableStateFlow(WhatsappFeed())
    val whatsapp: StateFlow<WhatsappFeed> = _whatsapp.asStateFlow()

    private val _outputTarget = MutableStateFlow("")
    val outputTarget: StateFlow<String> = _outputTarget.asStateFlow()

    private val _serverName = MutableStateFlow("Zaya")
    val serverName: StateFlow<String> = _serverName.asStateFlow()

    private val _voice = MutableStateFlow(VoiceState())
    val voice: StateFlow<VoiceState> = _voice.asStateFlow()

    private var lastZayaLine: Pair<String, Long>? = null
    private var deviceId: String = ""
    private val recentNotifications = LinkedHashMap<String, Long>()

    val unread: Int get() = _notifications.value.count { !it.read }

    // ── laptop events ────────────────────────────────────────────────────────

    /** Fold one envelope into the screen state. Never throws, never trusts input. */
    @Synchronized
    fun apply(envelope: Envelope): List<RuntimeEffect> {
        val payload = envelope.payload
        return when (envelope.type) {
            Protocol.Type.HELLO -> {
                patchHello(payload)
                when (val current = _call.value) {
                    is CallUiState.Active -> listOf(RuntimeEffect.StartVoice)
                    is CallUiState.Dialing -> listOf(RuntimeEffect.Ringback)
                    is CallUiState.Ringing -> listOf(RuntimeEffect.Ring(current.call))
                    CallUiState.Idle -> emptyList()
                }
            }

            Protocol.Type.STATE -> {
                _visual.value = ZayaVisual(
                    state = Protocol.normalizeState(payload.str("state", 40)),
                    emotion = Protocol.normalizeEmotion(payload.str("emotion", 20)),
                )
                if (_visual.value.state != Protocol.SPEAKING) _caption.value = Caption()
                emptyList()
            }

            Protocol.Type.CAPTION -> {
                val text = payload.str("text", Protocol.MAX_CAPTION)
                if (text.isNotEmpty()) _caption.value = Caption(text, clock())
                emptyList()
            }

            Protocol.Type.CHAT -> {
                applyChat(payload)
                emptyList()
            }

            Protocol.Type.COMMAND_STATUS -> {
                applyCommandStatus(payload)
                emptyList()
            }

            Protocol.Type.TASK_CREATED,
            Protocol.Type.TASK_UPDATED,
            Protocol.Type.TASK_COMPLETED,
            Protocol.Type.TASK_FAILED,
            Protocol.Type.TASK_CANCELLED,
            -> {
                applyTask(envelope.type, payload)
                emptyList()
            }

            Protocol.Type.WHATSAPP_MESSAGE -> {
                applyWhatsappMessage(payload)
            }

            Protocol.Type.WHATSAPP_ALERT -> {
                applyWhatsappAlert(payload)
            }

            Protocol.Type.WHATSAPP_MODE -> {
                val scope = payload.str("scope", 40)
                val mode = payload.str("mode", 40)
                val current = _whatsapp.value
                _whatsapp.value = current.copy(
                    globalMode = if (scope == "chat") current.globalMode else mode,
                    chatId = payload.str("chat_id", Protocol.MAX_REFERENCE),
                    chatMode = if (scope == "chat") mode else current.chatMode,
                    aiActive = payload.flag("ai_active", current.aiActive),
                    feedReady = payload.flag("feed_ready", current.feedReady),
                )
                // A mode change is the owner's own action: tell the UI, do not buzz.
                emptyList()
            }

            Protocol.Type.WARNING -> {
                val text = payload.str("text", Protocol.MAX_DETAIL)
                if (text.isEmpty()) return emptyList()
                val item = notification(
                    key = "warning:${envelope.timestamp}",
                    title = "Zaya needs you",
                    body = text,
                    priority = Protocol.P2_IMPORTANT,
                    priorityName = "important",
                    source = "system",
                    quiet = false,
                    severity = payload.str("severity", 20),
                )
                listOfNotNull(item).map { RuntimeEffect.Notify(it) }
            }

            Protocol.Type.NOTIFY, Protocol.Type.NOTIFICATION -> {
                val item = notification(
                    key = payload.str("key", Protocol.MAX_REFERENCE)
                        .ifBlank { "notify:${envelope.timestamp}" },
                    title = payload.str("title", Protocol.MAX_TITLE).ifBlank { "Zaya" },
                    body = payload.str("body", Protocol.MAX_DETAIL),
                    priority = payload.optInt("priority", Protocol.P2_IMPORTANT),
                    priorityName = payload.str("priority_name", 20),
                    source = payload.str("source", 40),
                    quiet = payload.flag("quiet"),
                    severity = payload.str("severity", 20),
                )
                listOfNotNull(item).map { RuntimeEffect.Notify(it) }
            }

            Protocol.Type.CALL_INCOMING -> applyIncomingCall(payload)

            Protocol.Type.CALL_DIALING -> {
                val call = CallInfo.from(payload)
                if (call.callId.isEmpty() || !belongsHere(call)) return emptyList()
                _call.value = CallUiState.Dialing(call)
                setVoice(micActive = false, speakerActive = false, muted = false)
                listOf(RuntimeEffect.Ringback)
            }

            Protocol.Type.CALL_ANSWERED -> {
                val call = CallInfo.from(payload)
                if (call.callId.isEmpty()) return emptyList()
                if (!belongsHere(call)) {
                    _call.value = CallUiState.Idle
                    setVoice(micActive = false, speakerActive = false)
                    return listOf(RuntimeEffect.StopVoice, RuntimeEffect.StopRinging)
                }
                _call.value = CallUiState.Active(call, clock())
                setVoice(micActive = true, speakerActive = true)
                listOf(RuntimeEffect.StartVoice, RuntimeEffect.StopRinging)
            }

            Protocol.Type.CALL_ENDED, Protocol.Type.CALL_MISSED -> applyCallEnd(
                envelope.type,
                payload,
            )

            Protocol.Type.ERROR -> {
                val text = payload.str("error", Protocol.MAX_DETAIL)
                if (text.isNotEmpty()) notice(text)
                emptyList()
            }

            else -> emptyList()
        }
    }

    /** The first paint after a reconnect, straight from the laptop's own snapshot. */
    @Synchronized
    fun applySnapshot(snapshot: JSONObject?) {
        if (snapshot == null) return
        _serverName.value = snapshot.str("server_name", 80).ifBlank { _serverName.value }
        _visual.value = ZayaVisual(
            state = Protocol.normalizeState(snapshot.str("state", 40)),
            emotion = Protocol.normalizeEmotion(snapshot.str("emotion", 20)),
        )
        val caption = snapshot.str("caption", Protocol.MAX_CAPTION)
        _caption.value = if (caption.isEmpty()) Caption() else Caption(caption, clock())
        _outputTarget.value = snapshot.str("output_target", 40)
        val active = snapshot.child("active_call")
        _call.value = if (active != null) {
            val call = CallInfo.from(active)
            if (call.callId.isNotEmpty() && call.state == CallInfo.STATE_ANSWERED && belongsHere(call)) {
                setVoice(micActive = true, speakerActive = true)
                CallUiState.Active(call, clock())
            } else if (call.callId.isNotEmpty() && call.state == CallInfo.STATE_RINGING) {
                setVoice(micActive = false, speakerActive = false)
                if (call.direction == "outgoing") {
                    if (belongsHere(call)) CallUiState.Dialing(call) else CallUiState.Idle
                } else CallUiState.Ringing(call)
            } else {
                CallUiState.Idle
            }
        } else {
            CallUiState.Idle
        }
        snapshot.array("tasks")?.let { array ->
            val rows = ArrayList<TaskItem>(array.length())
            for (index in 0 until array.length()) {
                val row = array.optJSONObject(index) ?: continue
                val task = TaskItem.from(row)
                if (task.taskId.isNotEmpty()) rows += task
            }
            _tasks.value = rows.sortedByDescending { it.updatedAt }.take(Protocol.MAX_TASK_ROWS)
        }
    }

    // ── owner actions (local echo; the laptop stays the authority) ───────────

    /** Adds the owner's line optimistically and returns the request id to send. */
    @Synchronized
    fun beginCommand(text: String): Pair<String, ChatLine>? {
        val clipped = Protocol.clip(text, Protocol.MAX_TEXT)
        if (clipped.isEmpty()) return null
        val requestId = tracker.requestIdFor(clipped)
        val existing = _chat.value.firstOrNull { it.id == requestId }
        if (existing != null) return requestId to existing
        val line = ChatLine(
            id = requestId,
            speaker = Speaker.OWNER,
            text = clipped,
            at = clock(),
            status = Protocol.STATUS_SUBMITTED,
            source = "phone",
        )
        appendLine(line)
        return requestId to line
    }

    @Synchronized
    fun markCommandQueued(requestId: String) {
        tracker.update(requestId, Protocol.STATUS_SUBMITTED)
        updateLine(requestId) { it.copy(status = Protocol.STATUS_SUBMITTED, error = "") }
    }

    /** The laptop's acknowledgement reached the phone. */
    @Synchronized
    fun markCommandSent(requestId: String) {
        updateLine(requestId) { line ->
            if (line.status == Protocol.STATUS_SUBMITTED) line.copy(status = "sent") else line
        }
    }

    @Synchronized
    fun notice(text: String, status: String = "") {
        if (text.isBlank()) return
        appendLine(
            ChatLine(
                id = "notice:${clock()}:${_chat.value.size}",
                speaker = Speaker.NOTICE,
                text = Protocol.clip(text, Protocol.MAX_DETAIL),
                at = clock(),
                status = status,
            ),
        )
    }

    @Synchronized
    fun markCommandFailedLocally(requestId: String, error: String) {
        tracker.update(requestId, Protocol.STATUS_FAILED)
        updateLine(requestId) { it.copy(status = Protocol.STATUS_FAILED, error = error) }
    }

    @Synchronized
    fun setOutputTarget(target: String) {
        _outputTarget.value = target
    }

    /** The laptop's own task list, used for the first paint and on refresh. */
    @Synchronized
    fun mergeTasks(rows: List<TaskItem>) {
        if (rows.isEmpty()) return
        val merged = _tasks.value.associateBy { it.taskId }.toMutableMap()
        for (row in rows) merged[row.taskId] = row
        _tasks.value = merged.values.sortedByDescending { it.updatedAt }
            .take(Protocol.MAX_TASK_ROWS)
    }

    /** A WhatsApp answer from the laptop, verbatim. */
    @Synchronized
    fun setWhatsapp(feed: WhatsappFeed) {
        _whatsapp.value = feed
    }

    @Synchronized
    fun setServerName(name: String) {
        if (name.isNotBlank()) _serverName.value = name
    }

    @Synchronized
    fun setVoice(
        micActive: Boolean = _voice.value.micActive,
        speakerActive: Boolean = _voice.value.speakerActive,
        muted: Boolean = _voice.value.muted,
        note: String = _voice.value.note,
    ) {
        _voice.value = VoiceState(micActive, speakerActive, muted, note)
    }

    @Synchronized
    fun markNotificationsRead() {
        if (_notifications.value.isEmpty()) return
        _notifications.value = _notifications.value.map { it.copy(read = true) }
    }

    @Synchronized
    fun clearComposer() {
        lastZayaLine = null
    }

    /** The phone went offline: keep the transcript, admit the link is down. */
    @Synchronized
    fun connectionLost(reason: String) {
        if (_call.value is CallUiState.Active) {
            notice("Call dropped: $reason")
        }
        _call.value = CallUiState.Idle
        setVoice(micActive = false, speakerActive = false)
    }

    @Synchronized
    fun expiredCaption(now: Long): Boolean {
        val current = _caption.value
        if (current.text.isEmpty()) return false
        if (now - current.at <= CAPTION_TTL_MILLIS) return false
        _caption.value = Caption()
        return true
    }

    // ── internals ────────────────────────────────────────────────────────────

    private fun patchHello(payload: JSONObject) {
        deviceId = payload.str("device_id", 128)
        _serverName.value = payload.str("server", 80).ifBlank { _serverName.value }
        applySnapshot(payload.child("snapshot"))
    }

    private fun belongsHere(call: CallInfo): Boolean =
        call.deviceId.isEmpty() || (deviceId.isNotEmpty() && call.deviceId == deviceId)

    private fun applyChat(payload: JSONObject) {
        val text = payload.str("text", Protocol.MAX_TEXT)
        if (text.isEmpty()) return
        val role = payload.str("role", 20).lowercase()
        val requestId = payload.str("request_id", 120)
        if (role == "user") {
            // Our own line coming back: adopt the laptop's copy, never add a twin.
            if (requestId.isNotEmpty() && _chat.value.any { it.id == requestId }) {
                markCommandSent(requestId)
                return
            }
            val line = ChatLine(
                id = requestId.ifEmpty { "user:${clock()}:${_chat.value.size}" },
                speaker = Speaker.OWNER,
                text = text,
                at = clock(),
                status = "sent",
                source = payload.str("source", 40),
            )
            appendLine(line)
            return
        }
        // Zaya's own words. The same utterance can arrive on two bus topics, so
        // an identical line within a moment is folded instead of repeated.
        val now = clock()
        val previous = lastZayaLine
        if (previous != null && previous.first == text && now - previous.second < ZAYA_DEDUPE_MILLIS) {
            return
        }
        lastZayaLine = text to now
        appendLine(
            ChatLine(
                id = "zaya:$now:${_chat.value.size}",
                speaker = Speaker.ZAYA,
                text = text,
                at = now,
            ),
        )
    }

    private fun applyCommandStatus(payload: JSONObject) {
        val requestId = payload.str("request_id", 120)
        val status = payload.str("status", 40)
        val text = payload.str("text", Protocol.MAX_TEXT)
        val error = payload.str("error", Protocol.MAX_DETAIL)
        if (requestId.isEmpty()) return
        tracker.update(requestId, status)
        if (_chat.value.none { it.id == requestId } && text.isNotEmpty()) {
            appendLine(
                ChatLine(
                    id = requestId,
                    speaker = Speaker.OWNER,
                    text = text,
                    at = clock(),
                    source = "phone",
                ),
            )
        }
        updateLine(requestId) { it.copy(status = status, error = error) }
    }

    private fun applyTask(type: String, payload: JSONObject) {
        val task = TaskItem.from(payload.child("task") ?: return)
        if (task.taskId.isEmpty()) return
        val rows = _tasks.value.toMutableList()
        val index = rows.indexOfFirst { it.taskId == task.taskId }
        if (index >= 0) rows[index] = task else rows.add(0, task)
        _tasks.value = rows.sortedByDescending { it.updatedAt }.take(Protocol.MAX_TASK_ROWS)
        if (type == Protocol.Type.TASK_COMPLETED) {
            notice("Task finished: ${task.goal}")
        } else if (type == Protocol.Type.TASK_FAILED) {
            notice(
                "Task failed: ${task.goal}" + (task.error?.let { " — $it" } ?: ""),
                status = Protocol.STATUS_FAILED,
            )
        } else if (type == Protocol.Type.TASK_CANCELLED) {
            notice("Task stopped: ${task.goal}")
        }
    }

    private fun applyWhatsappMessage(payload: JSONObject): List<RuntimeEffect> {
        val chatId = payload.str("chat_id", Protocol.MAX_REFERENCE)
        val title = payload.str("title", Protocol.MAX_TITLE).ifBlank { "WhatsApp" }
        val important = payload.flag("important")
        val row = WhatsappRow(
            chatId = chatId,
            title = title,
            summary = _whatsapp.value.summary,
            important = important,
        )
        _whatsapp.value = _whatsapp.value.copy(rows = (listOf(row) + _whatsapp.value.rows)
            .distinctBy { it.chatId }
            .take(MAX_WHATSAPP_ROWS))
        if (!important) return emptyList()
        val item = notification(
            key = "wa:${chatId}:${payload.str("message_id", Protocol.MAX_REFERENCE)}",
            title = "WhatsApp · $title",
            body = "Something important arrived. Open the laptop's Zaya to read it.",
            priority = Protocol.P2_IMPORTANT,
            priorityName = "important",
            source = "whatsapp",
            quiet = false,
        ) ?: return emptyList()
        return listOf(RuntimeEffect.Notify(item))
    }

    private fun applyWhatsappAlert(payload: JSONObject): List<RuntimeEffect> {
        val alertId = payload.str("alert_id", Protocol.MAX_REFERENCE)
        val title = payload.str("title", Protocol.MAX_TITLE).ifBlank { "WhatsApp" }
        val row = WhatsappRow(
            chatId = payload.str("chat_id", Protocol.MAX_REFERENCE),
            title = title,
            summary = payload.str("reason", Protocol.MAX_DETAIL),
            score = payload.optInt("score", 0),
            category = payload.str("category", 40),
            important = true,
            reason = payload.str("reason", Protocol.MAX_DETAIL),
        )
        _whatsapp.value = _whatsapp.value.copy(
            rows = (listOf(row) + _whatsapp.value.rows).take(MAX_WHATSAPP_ROWS),
        )
        val item = notification(
            key = "wa-alert:${alertId.ifEmpty { title + payload.optInt("score", 0) }}",
            title = "WhatsApp · $title",
            body = row.reason.ifBlank { "A message was flagged as important." },
            priority = Protocol.P2_IMPORTANT,
            priorityName = "important",
            source = "whatsapp",
            quiet = false,
        ) ?: return emptyList()
        return listOf(RuntimeEffect.Notify(item))
    }

    private fun applyIncomingCall(payload: JSONObject): List<RuntimeEffect> {
        val call = CallInfo.from(payload)
        if (call.callId.isEmpty()) return emptyList()
        if (!Protocol.ringsOnPhone(call.priority)) {
            // P2/P3: the laptop's own notify event carries the visible part, and a
            // lower-priority call must never take over the screen. Remember it so
            // the owner can still start talking if they want to.
            val item = notification(
                key = "call:${call.callId}",
                title = call.title.ifBlank { "Zaya tried to call" },
                body = call.detail.ifBlank { call.reason },
                priority = call.priority,
                priorityName = call.priorityName,
                source = call.source,
                quiet = call.priority >= Protocol.P3_NORMAL,
            )
            return listOfNotNull(item).map { RuntimeEffect.Notify(it) }
        }
        _call.value = CallUiState.Ringing(call)
        setVoice(micActive = false, speakerActive = false)
        return listOf(RuntimeEffect.Ring(call))
    }

    private fun applyCallEnd(type: String, payload: JSONObject): List<RuntimeEffect> {
        val call = CallInfo.from(payload)
        val current = _call.value
        val currentId = when (current) {
            is CallUiState.Active -> current.call.callId
            is CallUiState.Ringing -> current.call.callId
            is CallUiState.Dialing -> current.call.callId
            CallUiState.Idle -> ""
        }
        if (currentId.isNotEmpty() && call.callId.isNotEmpty() && currentId != call.callId) {
            return emptyList()
        }
        val answeredAt = when (current) {
            is CallUiState.Active -> current.answeredAt
            else -> 0L
        }
        val outcome = payload.str("outcome", 40)
        if (type == Protocol.Type.CALL_MISSED) {
            val summary = payload.str("summary", Protocol.MAX_DETAIL)
                .ifBlank { call.detail.ifBlank { call.title } }
            val since = call.detail.ifBlank { call.title }
            notice(
                text = "Missed call from Zaya: " + summary + if (since.isNotBlank()) " ($since)" else "",
                status = Protocol.STATUS_FAILED,
            )
        } else if (answeredAt > 0L) {
            val seconds = ((clock() - answeredAt) / 1000).coerceAtLeast(0)
            notice("Call ended (${formatDuration(seconds)})" + if (outcome.isNotBlank()) " · $outcome" else "")
        } else {
            notice("Call ended" + if (outcome.isNotBlank()) " · $outcome" else "")
        }
        _call.value = CallUiState.Idle
        setVoice(micActive = false, speakerActive = false)
        return listOf(RuntimeEffect.StopVoice, RuntimeEffect.StopRinging)
    }

    private fun notification(
        key: String,
        title: String,
        body: String,
        priority: Int,
        priorityName: String,
        source: String,
        quiet: Boolean,
        severity: String = "",
    ): NotificationItem? {
        val now = clock()
        if (title.isBlank() && body.isBlank()) return null
        val fingerprint = "$title|$body"
        val seen = recentNotifications[fingerprint]
        if (seen != null && now - seen < NOTIFICATION_DEDUPE_MILLIS) return null
        recentNotifications[fingerprint] = now
        while (recentNotifications.size > 50) {
            val oldest = recentNotifications.keys.firstOrNull() ?: break
            recentNotifications.remove(oldest)
        }
        val item = NotificationItem(
            key = key,
            title = title,
            body = body,
            priority = priority,
            priorityName = priorityName,
            source = source,
            quiet = quiet,
            at = now,
            severity = severity,
        )
        _notifications.value = (listOf(item) + _notifications.value)
            .take(Protocol.MAX_NOTIFICATIONS)
        return item
    }

    private fun appendLine(line: ChatLine) {
        _chat.value = (_chat.value + line).takeLast(Protocol.MAX_CHAT_LINES)
    }

    private fun updateLine(id: String, transform: (ChatLine) -> ChatLine) {
        val rows = _chat.value
        val index = rows.indexOfFirst { it.id == id }
        if (index < 0) return
        val updated = rows.toMutableList()
        updated[index] = transform(rows[index])
        _chat.value = updated
    }

    companion object {
        const val CAPTION_TTL_MILLIS = 6_000L
        private const val ZAYA_DEDUPE_MILLIS = 1_500L
        private const val NOTIFICATION_DEDUPE_MILLIS = 5_000L
        private const val MAX_WHATSAPP_ROWS = 60

        fun formatDuration(seconds: Long): String {
            val minutes = seconds / 60
            val rest = seconds % 60
            return if (minutes > 0) "%d:%02d".format(minutes, rest) else "${rest}s"
        }
    }
}
