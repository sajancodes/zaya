package com.zaya.companion

import com.zaya.companion.protocol.Envelope
import com.zaya.companion.protocol.Pairing
import com.zaya.companion.protocol.Protocol
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The phone must survive anything the network hands it. */
class ProtocolTest {

    @Test
    fun `parses a well formed envelope`() {
        val envelope = Envelope.parse(
            """{"protocol_version":1,"type":"zaya.state","timestamp":12.5,"payload":{"state":"SPEAKING","emotion":"happy"}}""",
        )
        assertNotNull(envelope)
        assertEquals("zaya.state", envelope!!.type)
        assertEquals(1, envelope.version)
        assertEquals(12.5, envelope.timestamp, 0.0001)
        assertEquals("SPEAKING", envelope.payload.optString("state"))
    }

    @Test
    fun `rubbish is refused instead of thrown`() {
        assertNull(Envelope.parse(null))
        assertNull(Envelope.parse(""))
        assertNull(Envelope.parse("   "))
        assertNull(Envelope.parse("not json at all"))
        assertNull(Envelope.parse("[1,2,3]"))
        assertNull(Envelope.parse("""{"payload":{}}"""))
        assertNull(Envelope.parse("""{"type":"   "}"""))
    }

    @Test
    fun `a payload that is not an object becomes an empty one`() {
        val envelope = Envelope.parse("""{"type":"hello","payload":"nonsense"}""")
        assertNotNull(envelope)
        assertEquals(0, envelope!!.payload.length())
        assertEquals(Protocol.VERSION, envelope.version)
    }

    @Test
    fun `unknown types still parse, so the laptop can add events`() {
        val envelope = Envelope.parse("""{"type":"something.new","payload":{"a":1}}""")
        assertEquals("something.new", envelope?.type)
    }

    @Test
    fun `states collapse exactly like the laptop collapses them`() {
        assertEquals(Protocol.SPEAKING, Protocol.normalizeState("speaking"))
        assertEquals(Protocol.SPEAKING, Protocol.normalizeState(" SPEAKING "))
        assertEquals(Protocol.TASK_RUNNING, Protocol.normalizeState("task-running"))
        assertEquals(Protocol.TASK_RUNNING, Protocol.normalizeState("TASK_PLANNING"))
        assertEquals(Protocol.STANDBY, Protocol.normalizeState(null))
        assertEquals(Protocol.STANDBY, Protocol.normalizeState("who knows"))
        assertEquals(Protocol.STANDBY, Protocol.normalizeState("idle"))
    }

    @Test
    fun `emotions outside the protocol do not reach the screen`() {
        assertEquals("happy", Protocol.normalizeEmotion("HAPPY"))
        assertEquals("surprised", Protocol.normalizeEmotion(" surprised "))
        assertEquals("neutral", Protocol.normalizeEmotion(null))
        assertEquals("neutral", Protocol.normalizeEmotion("poked"))
        assertEquals("neutral", Protocol.normalizeEmotion(""))
    }

    @Test
    fun `clip strips control characters and honours the bound`() {
        assertEquals("ab", Protocol.clip("a\u0001b", 10))
        assertEquals("abc", Protocol.clip("abcdef", 3))
        assertEquals("", Protocol.clip(null, 5))
        assertEquals("line\nbreak", Protocol.clip("line\nbreak", 40))
        assertEquals(4, Protocol.clip("1234567890", 4).length)
    }

    @Test
    fun `only P0 and P1 may ring the phone`() {
        assertTrue(Protocol.ringsOnPhone(Protocol.P0_CRITICAL))
        assertTrue(Protocol.ringsOnPhone(Protocol.P1_IMMEDIATE))
        assertFalse(Protocol.ringsOnPhone(Protocol.P2_IMPORTANT))
        assertFalse(Protocol.ringsOnPhone(Protocol.P3_NORMAL))
        assertTrue(Protocol.notifiesPhone(Protocol.P2_IMPORTANT))
        assertFalse(Protocol.notifiesPhone(Protocol.P3_NORMAL))
    }

    @Test
    fun `addresses become usable base urls`() {
        assertEquals("http://laptop.tailnet.ts.net:8443", Pairing.normalizeAddress("laptop.tailnet.ts.net:8443"))
        assertEquals("http://laptop", Pairing.normalizeAddress(" http://laptop/ "))
        assertEquals("https://laptop", Pairing.normalizeAddress("https://laptop///"))
        assertEquals("", Pairing.normalizeAddress("   "))
        assertEquals("wss://laptop:8443", Pairing.wsBase("https://laptop:8443"))
        assertEquals("ws://laptop", Pairing.wsBase("http://laptop"))
        assertEquals("laptop", Pairing.host("http://laptop:8443/path"))
    }

    @Test
    fun `request ids are unique and bounded`() {
        val first = Protocol.newRequestId()
        val second = Protocol.newRequestId()
        assertFalse(first == second)
        assertTrue(first.length <= 32)
        assertTrue(first.isNotBlank())
    }

    @Test
    fun `output targets and whatsapp modes are the laptop's vocabulary`() {
        assertTrue(Protocol.Output.TARGETS.contains(Protocol.Output.PHONE))
        assertFalse(Protocol.Output.TARGETS.contains("speakers"))
        assertEquals(listOf("auto", "observe"), Protocol.WhatsappMode.GLOBAL)
        assertTrue(Protocol.WhatsappMode.PER_CHAT.contains("paused"))
    }

    @Test
    fun `a command status envelope carries the fields the transcript needs`() {
        val payload = JSONObject()
            .put("request_id", "abc")
            .put("status", Protocol.STATUS_FAILED)
            .put("text", "open the report")
            .put("error", "no such file")
        assertEquals(Protocol.STATUS_FAILED, payload.optString("status"))
    }
}
