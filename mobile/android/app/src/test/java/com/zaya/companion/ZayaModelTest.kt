package com.zaya.companion

import com.zaya.companion.protocol.CallUiState
import com.zaya.companion.protocol.Envelope
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.protocol.Speaker
import com.zaya.companion.runtime.RuntimeEffect
import com.zaya.companion.runtime.ZayaModel
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The phone renders; the laptop decides.
 *
 * Every test here is a laptop event going in and a screen coming out, with no
 * Android anywhere: if the phone ever invented a state of its own, this file is
 * where it would show up.
 */
class ZayaModelTest {

    private var now = 1_000_000L
    private val model = ZayaModel(clock = { now })

    private fun event(type: String, payload: JSONObject) =
        Envelope(type, payload, 0.0, Protocol.VERSION)

    @Test
    fun `outgoing call rings without opening the microphone until laptop answers`() {
        val payload = JSONObject().put("call_id", "out-1").put("state", "ringing")
            .put("direction", "outgoing").put("priority", 1)
        val effects = model.apply(event(Protocol.Type.CALL_DIALING, payload))
        assertTrue(model.call.value is CallUiState.Dialing)
        assertFalse(model.voice.value.micActive)
        assertEquals(listOf(RuntimeEffect.Ringback), effects)
        model.apply(event(Protocol.Type.CALL_ANSWERED, payload.put("state", "answered")))
        assertTrue(model.call.value is CallUiState.Active)
        assertTrue(model.voice.value.micActive)
        model.apply(event(Protocol.Type.CALL_ENDED, payload.put("state", "ended")))
        assertEquals(CallUiState.Idle, model.call.value)
        assertFalse(model.voice.value.micActive)
    }

    @Test
    fun `another phone answering cannot open this microphone`() {
        model.apply(event(Protocol.Type.HELLO, JSONObject().put("device_id", "mine")))
        model.apply(event(Protocol.Type.CALL_INCOMING,
            JSONObject().put("call_id", "in-1").put("priority", 1)))
        model.apply(event(Protocol.Type.CALL_ANSWERED,
            JSONObject().put("call_id", "in-1").put("device_id", "other")))
        assertEquals(CallUiState.Idle, model.call.value)
        assertFalse(model.voice.value.micActive)
    }

    @Test
    fun `hello snapshot restores ringing without inventing an answer`() {
        val call = JSONObject().put("call_id", "out-1").put("state", "ringing")
            .put("direction", "outgoing").put("device_id", "mine").put("priority", 1)
        val effects = model.apply(event(Protocol.Type.HELLO,
            JSONObject().put("device_id", "mine").put("snapshot",
                JSONObject().put("active_call", call))))
        assertTrue(model.call.value is CallUiState.Dialing)
        assertFalse(model.voice.value.micActive)
        assertEquals(listOf(RuntimeEffect.Ringback), effects)
    }

    @Test
    fun `late end event for an old call leaves current call alone`() {
        model.apply(event(Protocol.Type.CALL_DIALING,
            JSONObject().put("call_id", "new").put("direction", "outgoing")))
        val effects = model.apply(event(Protocol.Type.CALL_ENDED,
            JSONObject().put("call_id", "old")))
        assertTrue(model.call.value is CallUiState.Dialing)
        assertTrue(effects.isEmpty())
    }

    @Test
    fun `the laptop's state is the state on screen`() {
        model.apply(
            event(
                Protocol.Type.STATE,
                JSONObject().put("state", "speaking").put("emotion", "happy"),
            ),
        )

        assertEquals(Protocol.SPEAKING, model.visual.value.state)
        assertEquals("happy", model.visual.value.emotion)
    }

    @Test
    fun `an unknown event changes nothing and crashes nothing`() {
        val effects = model.apply(event("zaya.hologram", JSONObject().put("x", 1)))

        assertTrue(effects.isEmpty())
        assertEquals(Protocol.STANDBY, model.visual.value.state)
    }

    @Test
    fun `helloTM paints the first screen from the laptop's snapshot`() {
        val tasks = JSONArray().put(
            JSONObject()
                .put("task_id", "t1")
                .put("goal", "Book a table")
                .put("state", "executing")
                .put("updated_at", 9.0),
        )
        val snapshot = JSONObject()
            .put("server_name", "Zaya")
            .put("state", "THINKING")
            .put("emotion", "neutral")
            .put("caption", "looking at your inbox")
            .put("output_target", "desktop")
            .put("tasks", tasks)

        model.apply(
            event(
                Protocol.Type.HELLO,
                JSONObject().put("server", "Zaya").put("snapshot", snapshot),
            ),
        )

        assertEquals("Zaya", model.serverName.value)
        assertEquals(Protocol.THINKING, model.visual.value.state)
        assertEquals("looking at your inbox", model.caption.value.text)
        assertEquals("desktop", model.outputTarget.value)
        assertEquals(1, model.tasks.value.size)
        assertEquals("Book a table", model.tasks.value.first().goal)
    }

    @Test
    fun `the owner's own line is not duplicated by the laptop's echo`() {
        val started = model.beginCommand("open the monthly report")
        assertNotNull(started)
        val (requestId, line) = started!!

        model.apply(
            event(
                Protocol.Type.CHAT,
                JSONObject()
                    .put("role", "user")
                    .put("text", "open the monthly report")
                    .put("request_id", requestId),
            ),
        )

        assertEquals(1, model.chat.value.size)
        assertEquals(line.id, model.chat.value.first().id)
        assertEquals("sent", model.chat.value.first().status)
    }

    @Test
    fun `a command walks the laptop's statuses and lands on the error`() {
        val (requestId, _) = model.beginCommand("open the report")!!

        model.apply(
            event(
                Protocol.Type.COMMAND_STATUS,
                JSONObject()
                    .put("request_id", requestId)
                    .put("status", Protocol.STATUS_EXECUTING)
                    .put("text", "open the report"),
            ),
        )
        assertEquals(Protocol.STATUS_EXECUTING, model.chat.value.first().status)

        model.apply(
            event(
                Protocol.Type.COMMAND_STATUS,
                JSONObject()
                    .put("request_id", requestId)
                    .put("status", Protocol.STATUS_FAILED)
                    .put("text", "open the report")
                    .put("error", "no such file"),
            ),
        )
        assertEquals(Protocol.STATUS_FAILED, model.chat.value.first().status)
        assertEquals("no such file", model.chat.value.first().error)
        assertTrue(model.chat.value.first().isTerminal)
    }

    @Test
    fun `a status for a command this phone never sent still shows up`() {
        model.apply(
            event(
                Protocol.Type.COMMAND_STATUS,
                JSONObject()
                    .put("request_id", "from-the-dashboard")
                    .put("status", Protocol.STATUS_COMPLETED)
                    .put("text", "typed on the laptop"),
            ),
        )

        assertEquals(1, model.chat.value.size)
        assertEquals("typed on the laptop", model.chat.value.first().text)
        assertEquals(Protocol.STATUS_COMPLETED, model.chat.value.first().status)
    }

    @Test
    fun `the same utterance from two bus topics is folded into one line`() {
        val zaya = JSONObject().put("role", "assistant").put("text", "Done — it's open.")

        model.apply(event(Protocol.Type.CHAT, zaya))
        model.apply(event(Protocol.Type.CHAT, zaya))

        assertEquals(1, model.chat.value.count { it.speaker == Speaker.ZAYA })
    }

    @Test
    fun `a P0 call rings and a P2 call only notifies`() {
        val ring = model.apply(
            event(
                Protocol.Type.CALL_INCOMING,
                JSONObject()
                    .put("call_id", "c1")
                    .put("title", "Zaya needs you")
                    .put("priority", Protocol.P0_CRITICAL)
                    .put("priority_name", "critical"),
            ),
        )

        assertTrue(ring.any { it is RuntimeEffect.Ring })
        assertTrue(model.call.value is CallUiState.Ringing)

        val quiet = model.apply(
            event(
                Protocol.Type.CALL_INCOMING,
                JSONObject()
                    .put("call_id", "c2")
                    .put("title", "A quiet note")
                    .put("priority", Protocol.P2_IMPORTANT),
            ),
        )

        assertFalse(quiet.any { it is RuntimeEffect.Ring })
        assertTrue(quiet.any { it is RuntimeEffect.Notify })
    }

    @Test
    fun `answering starts the voice link and ending closes it`() {
        model.apply(
            event(
                Protocol.Type.CALL_INCOMING,
                JSONObject().put("call_id", "c1").put("priority", Protocol.P1_IMMEDIATE),
            ),
        )

        val answered = model.apply(
            event(
                Protocol.Type.CALL_ANSWERED,
                JSONObject().put("call_id", "c1").put("state", "answered"),
            ),
        )
        assertTrue(answered.any { it is RuntimeEffect.StartVoice })
        assertTrue(model.call.value is CallUiState.Active)
        assertTrue(model.voice.value.micActive)

        val ended = model.apply(
            event(
                Protocol.Type.CALL_ENDED,
                JSONObject().put("call_id", "c1").put("outcome", "completed"),
            ),
        )
        assertTrue(ended.any { it is RuntimeEffect.StopVoice })
        assertTrue(ended.any { it is RuntimeEffect.StopRinging })
        assertTrue(model.call.value is CallUiState.Idle)
        assertFalse(model.voice.value.micActive)
        assertTrue(model.chat.value.any { it.text.startsWith("Call ended") })
    }

    @Test
    fun `a missed call leaves one summary line and no redial`() {
        model.apply(
            event(
                Protocol.Type.CALL_MISSED,
                JSONObject()
                    .put("call_id", "c1")
                    .put("title", "Server is down")
                    .put("summary", "The staging box stopped answering")
                    .put("priority", Protocol.P1_IMMEDIATE),
            ),
        )

        val notices = model.chat.value.filter { it.speaker == Speaker.NOTICE }
        assertEquals(1, notices.size)
        assertTrue(notices.first().text.contains("staging box stopped answering"))
        assertTrue(model.call.value is CallUiState.Idle)
    }

    @Test
    fun `losing the link does not leave a call on screen`() {
        model.apply(
            event(
                Protocol.Type.CALL_INCOMING,
                JSONObject().put("call_id", "c1").put("priority", Protocol.P0_CRITICAL),
            ),
        )
        model.apply(
            event(Protocol.Type.CALL_ANSWERED, JSONObject().put("call_id", "c1")),
        )

        model.connectionLost("The laptop stopped answering")

        assertTrue(model.call.value is CallUiState.Idle)
        assertFalse(model.voice.value.micActive)
        assertTrue(model.chat.value.any { it.text.contains("Call dropped") })
    }

    @Test
    fun `tasks upsert by id and announce their ending`() {
        val task = JSONObject()
            .put("task_id", "t1")
            .put("goal", "Book a table")
            .put("state", "executing")
            .put("updated_at", 5.0)

        model.apply(event(Protocol.Type.TASK_CREATED, JSONObject().put("task", task)))
        assertEquals(1, model.tasks.value.size)
        assertEquals("executing", model.tasks.value.first().state)

        model.apply(
            event(
                Protocol.Type.TASK_COMPLETED,
                JSONObject().put("task", task.put("state", "completed").put("updated_at", 6.0)),
            ),
        )

        assertEquals(1, model.tasks.value.size)
        assertEquals("completed", model.tasks.value.first().state)
        assertTrue(model.chat.value.any { it.text.contains("Task finished: Book a table") })
    }

    @Test
    fun `a failed task says why`() {
        model.apply(
            event(
                Protocol.Type.TASK_FAILED,
                JSONObject().put(
                    "task",
                    JSONObject()
                        .put("task_id", "t2")
                        .put("goal", "Send the invoice")
                        .put("state", "failed")
                        .put("error", "the printer is out of paper")
                        .put("updated_at", 7.0),
                ),
            ),
        )

        assertFalse(model.tasks.value.first().isActive)
        assertTrue(model.chat.value.any { it.text.contains("the printer is out of paper") })
    }

    @Test
    fun `an important WhatsApp alert is quoted, never obeyed`() {
        val effects = model.apply(
            event(
                Protocol.Type.WHATSAPP_ALERT,
                JSONObject()
                    .put("alert_id", "a1")
                    .put("chat_id", "1234@s.whatsapp.net")
                    .put("title", "Mum")
                    .put("reason", "asks about the tickets")
                    .put("score", 82)
                    .put("category", "family"),
            ),
        )

        assertTrue(effects.any { it is RuntimeEffect.Notify })
        assertEquals(1, model.whatsapp.value.rows.size)
        assertEquals(82, model.whatsapp.value.rows.first().score)
    }

    @Test
    fun `the same notification twice is one notification`() {
        val payload = JSONObject()
            .put("title", "Missed Zaya call")
            .put("body", "The staging box stopped answering")
            .put("priority", Protocol.P2_IMPORTANT)

        val first = model.apply(event(Protocol.Type.NOTIFY, payload))
        val second = model.apply(event(Protocol.Type.NOTIFY, payload))

        assertEquals(1, first.size)
        assertTrue(second.isEmpty())
        assertEquals(1, model.notifications.value.size)
        assertEquals(1, model.unread)
    }

    @Test
    fun `read notifications stop counting as unread`() {
        model.apply(
            event(
                Protocol.Type.WARNING,
                JSONObject().put("text", "The mic is in use").put("severity", "warning"),
            ),
        )
        assertEquals(1, model.unread)

        model.markNotificationsRead()

        assertEquals(0, model.unread)
    }

    @Test
    fun `a caption fades instead of sitting there forever`() {
        model.apply(event(Protocol.Type.CAPTION, JSONObject().put("text", "give me a moment")))

        assertEquals("give me a moment", model.caption.value.text)
        assertFalse(model.expiredCaption(now))
        now += ZayaModel.CAPTION_TTL_MILLIS + 1
        assertTrue(model.expiredCaption(now))
        assertEquals("", model.caption.value.text)
    }

    @Test
    fun `a mute request is echoed back by the laptop, not invented here`() {
        model.setVoice(micActive = true, muted = true)
        assertTrue(model.voice.value.muted)
        assertTrue(model.voice.value.micActive)
    }
}
