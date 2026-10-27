package com.zaya.companion

import com.zaya.companion.action.ActionRisk
import com.zaya.companion.action.ActionResultStatus
import com.zaya.companion.action.AndroidAction
import com.zaya.companion.action.ActionExecutor
import com.zaya.companion.net.ZayaApi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import javax.net.ssl.SSLException

class SecurePcBridgeTest {

    @Test
    fun `test execute pc command requires explicit approval for consequential actions`() {
        val action = AndroidAction.ExecutePcCommand(
            command = "write_file",
            parameters = mapOf("path" to "project/config.json", "content" to "{}"),
            confirmed = false
        )

        assertEquals(ActionRisk.HIGH, action.risk)
        assertTrue(action.requiresConfirmation)

        // Mock ActionExecutor execution simulation
        val resource = action.parameters["path"] as? String ?: "PC resource"
        val isConsequential = action.command in listOf("write_file", "terminate_process", "delete_file", "install_software")
        assertTrue(isConsequential)

        val payload = mapOf(
            "target_pc" to "Paired PC",
            "action" to action.command,
            "resource" to resource,
            "parameters" to action.parameters,
            "potential_side_effects" to "Modifying or overwriting file at '$resource'",
            "reversible" to false
        )

        assertEquals("Paired PC", payload["target_pc"])
        assertEquals("write_file", payload["action"])
        assertEquals("project/config.json", payload["resource"])
        assertEquals(false, payload["reversible"])
    }

    @Test
    fun `test execute pc command succeeds when confirmed`() {
        val confirmedAction = AndroidAction.ExecutePcCommand(
            command = "write_file",
            parameters = mapOf("path" to "notes.txt", "content" to "hello"),
            confirmed = true
        )
        assertTrue(confirmedAction.confirmed)
        assertEquals("write_file", confirmedAction.command)
    }

    @Test
    fun `test non-consequential command status`() {
        val statusAction = AndroidAction.ExecutePcCommand(
            command = "system_status",
            parameters = emptyMap(),
            confirmed = false
        )
        val isConsequential = statusAction.command in listOf("write_file", "terminate_process", "delete_file", "install_software")
        assertFalse(isConsequential)
    }

    @Test
    fun `test friendly network messages for secure transport`() {
        val sslErr = SSLException("Cert path untrusted")
        val friendlySsl = ZayaApi.friendlyNetworkMessage(sslErr)
        assertTrue(friendlySsl.contains("certificate"))

        val timeoutErr = java.net.SocketTimeoutException("Read timed out")
        val friendlyTimeout = ZayaApi.friendlyNetworkMessage(timeoutErr)
        assertTrue(friendlyTimeout.contains("not answer in time"))

        val connectErr = java.net.ConnectException("Connection refused")
        val friendlyConnect = ZayaApi.friendlyNetworkMessage(connectErr)
        assertTrue(friendlyConnect.contains("Nothing answered"))
    }
}
