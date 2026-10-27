package com.zaya.companion

import com.zaya.companion.protocol.Envelope
import com.zaya.companion.protocol.Protocol
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MediaAndAppLauncherTest {

    @Test
    fun `media control envelope parses correctly`() {
        val json = """
            {
                "protocol_version": 1,
                "type": "mobile.media_control",
                "timestamp": 123.45,
                "payload": {
                    "action": "pause"
                }
            }
        """.trimIndent()

        val env = Envelope.parse(json)
        assertNotNull(env)
        assertEquals(Protocol.Type.MEDIA_CONTROL, env!!.type)
        assertEquals("pause", env.payload.optString("action"))
    }

    @Test
    fun `deep link envelope parses with target app and query`() {
        val json = """
            {
                "protocol_version": 1,
                "type": "mobile.deep_link",
                "timestamp": 123.45,
                "payload": {
                    "target_app": "youtube",
                    "query": "Believer Imagine Dragons"
                }
            }
        """.trimIndent()

        val env = Envelope.parse(json)
        assertNotNull(env)
        assertEquals(Protocol.Type.OPEN_DEEP_LINK, env!!.type)
        assertEquals("youtube", env.payload.optString("target_app"))
        assertEquals("Believer Imagine Dragons", env.payload.optString("query"))
    }

    @Test
    fun `launch app envelope parses application name`() {
        val json = """
            {
                "protocol_version": 1,
                "type": "mobile.launch_app",
                "timestamp": 123.45,
                "payload": {
                    "name": "Instagram"
                }
            }
        """.trimIndent()

        val env = Envelope.parse(json)
        assertNotNull(env)
        assertEquals(Protocol.Type.LAUNCH_APP, env!!.type)
        assertEquals("Instagram", env.payload.optString("name"))
    }

    @Test
    fun `protocol contains all personal mobile extension types`() {
        val types = setOf(
            Protocol.Type.CALL_CONTROL,
            Protocol.Type.NOTIFICATION_LISTENER,
            Protocol.Type.HARDWARE_ACTION,
            Protocol.Type.CALL_ANNOUNCE,
            Protocol.Type.AUTO_REPLY,
            Protocol.Type.DEVICE_STATUS,
            Protocol.Type.DOUBLE_CLAP_CONFIG,
            Protocol.Type.MEDIA_CONTROL,
            Protocol.Type.OPEN_DEEP_LINK,
            Protocol.Type.LAUNCH_APP,
        )
        for (t in types) {
            assertTrue("Type $t must not be blank", t.isNotBlank())
        }
    }
}
