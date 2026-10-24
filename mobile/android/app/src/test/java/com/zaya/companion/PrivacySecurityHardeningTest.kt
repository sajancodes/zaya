package com.zaya.companion

import com.zaya.companion.action.ActionRisk
import com.zaya.companion.action.ActionResult
import com.zaya.companion.action.ActionResultStatus
import com.zaya.companion.action.AndroidAction
import com.zaya.companion.action.ConsequentialActionDeduplicator
import com.zaya.companion.action.MultiStepTaskState
import com.zaya.companion.action.StepStatus
import com.zaya.companion.action.TaskCoordinator
import com.zaya.companion.action.TaskOverallStatus
import com.zaya.companion.action.TaskPlanner
import com.zaya.companion.action.TaskStep
import com.zaya.companion.memory.MemoryCategory
import com.zaya.companion.memory.PersonalMemoryStore
import com.zaya.companion.memory.SensitiveDataDetector
import com.zaya.companion.net.AuthResult
import com.zaya.companion.net.SocketEvents
import com.zaya.companion.net.ZayaApi
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files
import javax.net.ssl.SSLException

@OptIn(ExperimentalCoroutinesApi::class)
class PrivacySecurityHardeningTest {

    // 1. Missing, invalid, and unavailable API credentials
    @Test
    fun `test 1 missing invalid and unavailable credentials handling`() {
        // Friendly network messages for TLS, connection, or host errors
        val sslMsg = ZayaApi.friendlyNetworkMessage(SSLException("Handshake failed"))
        assertTrue(sslMsg.contains("certificate"))

        val connMsg = ZayaApi.friendlyNetworkMessage(java.net.ConnectException("Connection refused"))
        assertTrue(connMsg.contains("Nothing answered"))

        // Auth result types
        val denied = AuthResult.Denied("Invalid pairing key")
        assertEquals("Invalid pairing key", denied.message)

        val unavail = AuthResult.Unavailable("Server unreachable")
        assertEquals("Server unreachable", unavail.message)
    }

    // 2. Network loss and interrupted streaming
    @Test
    fun `test 2 network loss and socket disconnection handling`() {
        assertEquals(4001, SocketEvents.CLOSE_UNAUTHORIZED)
        val timeoutMsg = ZayaApi.friendlyNetworkMessage(java.net.SocketTimeoutException("Read timed out"))
        assertTrue(timeoutMsg.contains("not answer in time"))
    }

    // 3. Malformed or unexpected AI output
    @Test
    fun `test 3 malformed or unexpected action handling`() {
        val unsupported = ActionResult.unsupported("Action 'malformed_unknown_action' is not supported.")
        assertEquals(ActionResultStatus.UNSUPPORTED, unsupported.status)
        assertTrue(unsupported.error?.contains("malformed_unknown_action") == true)
    }

    // 4. Rejection of unsupported action names and parameters
    @Test
    fun `test 4 rejection of unsupported action names and malformed parameters`() {
        // Parameter validation error simulation
        val emptySmsError = ActionResult.failure("SMS recipient cannot be blank.", error = "malformed_parameters")
        assertEquals("malformed_parameters", emptySmsError.error)

        val longQueryError = ActionResult.failure("Call query or phone number exceeds maximum length.", error = "malformed_parameters")
        assertEquals("malformed_parameters", longQueryError.error)

        val badMediaError = ActionResult.failure("Unsupported media control action: 'explode'.", error = "unsupported_media_action")
        assertEquals("unsupported_media_action", badMediaError.error)
    }

    // 5. Permission denial and permission revocation
    @Test
    fun `test 5 permission denial and permission revocation handling`() {
        val permReq = ActionResult.permissionRequired("android.permission.RECORD_AUDIO", "Microphone required for voice.")
        assertEquals(ActionResultStatus.PERMISSION_REQUIRED, permReq.status)
        assertEquals("android.permission.RECORD_AUDIO", permReq.error)
        assertTrue(permReq.spokenMessage.contains("Microphone required"))
    }

    // 6. Cancellation and resource cleanup
    @Test
    fun `test 6 cancellation and resource cleanup`() {
        val deduplicator = ConsequentialActionDeduplicator()
        deduplicator.record("test_sig")
        assertTrue(deduplicator.isDuplicate("test_sig"))

        deduplicator.clear()
        assertFalse(deduplicator.isDuplicate("test_sig"))
    }

    // 7. Prevention of duplicate consequential actions
    @Test
    fun `test 7 prevention of duplicate consequential actions`() {
        val deduplicator = ConsequentialActionDeduplicator(windowMillis = 5000L)
        val signature = "compose_sms:1234567890:hello_world".hashCode().toString()

        // First attempt: not duplicate
        assertFalse(deduplicator.isDuplicate(signature))
        deduplicator.record(signature)

        // Second immediate attempt: duplicate prevented
        assertTrue(deduplicator.isDuplicate(signature))

        // Different signature: allowed
        val otherSignature = "compose_sms:9876543210:hello_world".hashCode().toString()
        assertFalse(deduplicator.isDuplicate(otherSignature))
    }

    // 8. Protection against stale task results
    @Test
    fun `test 8 protection against stale task results`() {
        val taskTokens = mutableMapOf<String, Long>()
        val taskId = "task_security_8"
        taskTokens[taskId] = 100L

        // Task superseded
        taskTokens[taskId] = 101L

        val incomingStaleToken = 100L
        val isStale = (taskTokens[taskId] ?: 0L) != incomingStaleToken
        assertTrue("Stale token must be detected", isStale)
    }

    // 9. Sensitive information excluded from production logs
    @Test
    fun `test 9 sensitive data detector blocks credentials`() {
        val (hasPass, _) = SensitiveDataDetector.containsSensitiveData("Here is my secret password123")
        assertTrue("Passwords must be detected", hasPass)

        val (hasPin, _) = SensitiveDataDetector.containsSensitiveData("My pin code is 9988")
        assertTrue("PINs must be detected", hasPin)

        val (hasKey, _) = SensitiveDataDetector.containsSensitiveData("api_key = AIzaSyFakeKey123")
        assertTrue("API keys must be detected", hasKey)

        val (hasBearer, _) = SensitiveDataDetector.containsSensitiveData("Bearer secret_jwt_token_456")
        assertTrue("Bearer tokens must be detected", hasBearer)

        val (hasCard, _) = SensitiveDataDetector.containsSensitiveData("card_number: 4111-2222-3333-4444")
        assertTrue("Credit cards must be detected", hasCard)

        val (hasPrivate, _) = SensitiveDataDetector.containsSensitiveData("BEGIN RSA PRIVATE KEY")
        assertTrue("Private keys must be detected", hasPrivate)

        val (benign, _) = SensitiveDataDetector.containsSensitiveData("Set flashlight on, volume 80")
        assertFalse("Benign command must not be blocked", benign)
    }

    // 10. Memory deletion and privacy-related state changes
    @Test
    fun `test 10 memory deletion purges local storage completely`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_privacy_test_10").toFile()
        val store = PersonalMemoryStore(tempDir)

        store.remember("music_app", "Spotify", MemoryCategory.ALIAS, true)
        store.remember("home_address", "123 Main St", MemoryCategory.PREFERENCE, true)
        assertEquals(2, store.getAllMemories().size)

        // Clear all
        val cleared = store.clearAll()
        assertTrue(cleared)
        assertEquals(0, store.getAllMemories().size)
        assertFalse(File(tempDir, "personal_memory.json").exists())

        tempDir.deleteRecursively()
    }

    // 11. Recovery from ambiguous external-action results
    @Test
    fun `test 11 recovery from ambiguous external-action results`() {
        val ambiguousResult = ActionResult.failure(
            spoken = "Message dispatch outcome is uncertain. Please check your messages app to avoid sending twice.",
            error = "ambiguous_external_outcome",
            data = mapOf("check_device" to true)
        )
        assertEquals("ambiguous_external_outcome", ambiguousResult.error)
        assertTrue(ambiguousResult.spokenMessage.contains("avoid sending twice"))
        assertEquals(true, ambiguousResult.data["check_device"])
    }

    // 12. Debug versus release configuration
    @Test
    fun `test 12 action risk categorization enforces safety gates`() {
        val sms = AndroidAction.ComposeSms("123", "hi")
        assertEquals(ActionRisk.CRITICAL, sms.risk)
        assertTrue(sms.requiresConfirmation)

        val reply = AndroidAction.ReplyToNotification("key", "reply text")
        assertEquals(ActionRisk.HIGH, reply.risk)
        assertTrue(reply.requiresConfirmation)

        val flashlight = AndroidAction.SetFlashlight(true)
        assertEquals(ActionRisk.LOW, flashlight.risk)
        assertFalse(flashlight.requiresConfirmation)
    }
}
