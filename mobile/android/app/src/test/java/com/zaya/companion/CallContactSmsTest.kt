package com.zaya.companion

import com.zaya.companion.action.ActionRisk
import com.zaya.companion.action.ActionResult
import com.zaya.companion.action.ActionResultStatus
import com.zaya.companion.action.AndroidAction
import com.zaya.companion.service.CallOperationResult
import com.zaya.companion.service.ContactLookupResult
import com.zaya.companion.service.ContactRecord
import com.zaya.companion.service.IncomingCallInfo
import com.zaya.companion.service.OutgoingCallOutcome
import com.zaya.companion.service.PhoneNumberInfo
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CallContactSmsTest {

    @Test
    fun `initiate call action requires confirmation and has high risk`() {
        val action = AndroidAction.InitiateCall("John", directCall = false, confirmed = false)
        assertEquals("initiate_call", action.actionId)
        assertEquals(ActionRisk.HIGH, action.risk)
        assertTrue(action.requiresConfirmation)
        assertEquals("John", action.queryOrNumber)
        assertFalse(action.directCall)
        assertFalse(action.confirmed)
    }

    @Test
    fun `get incoming call state action has low risk and no confirmation`() {
        val action = AndroidAction.GetIncomingCallState
        assertEquals("get_incoming_call_state", action.actionId)
        assertEquals(ActionRisk.LOW, action.risk)
        assertFalse(action.requiresConfirmation)
    }

    @Test
    fun `set caller announcement action toggles tts announcer`() {
        val action = AndroidAction.SetCallerAnnouncement(enabled = true)
        assertEquals("set_caller_announcement", action.actionId)
        assertEquals(ActionRisk.LOW, action.risk)
        assertFalse(action.requiresConfirmation)
        assertTrue(action.enabled)
    }

    @Test
    fun `compose sms action requires confirmation and has critical risk`() {
        val action = AndroidAction.ComposeSms(
            recipient = "Alice",
            message = "Arriving in 10 minutes",
            confirmed = false,
            directSend = false
        )
        assertEquals("compose_sms", action.actionId)
        assertEquals(ActionRisk.CRITICAL, action.risk)
        assertTrue(action.requiresConfirmation)
        assertEquals("Alice", action.recipient)
        assertEquals("Arriving in 10 minutes", action.message)
        assertFalse(action.confirmed)
        assertFalse(action.directSend)
    }

    @Test
    fun `contact lookup outcome data formats properly for single and ambiguous matches`() {
        val single = ContactRecord(
            contactId = "101",
            displayName = "John Doe",
            numbers = listOf(PhoneNumberInfo("+15550199", "Mobile", isPrimary = true))
        )
        val singleResult = ContactLookupResult.SingleMatch(single)
        assertTrue(singleResult is ContactLookupResult.SingleMatch)
        assertEquals("John Doe", singleResult.contact.displayName)
        assertEquals("+15550199", singleResult.contact.numbers.first().number)

        val ambiguous = ContactLookupResult.AmbiguousMatches(
            query = "John",
            candidates = listOf(
                single,
                ContactRecord("102", "John Smith", listOf(PhoneNumberInfo("+15550200", "Work")))
            )
        )
        assertEquals(2, ambiguous.candidates.size)
        assertEquals("John Smith", ambiguous.candidates[1].displayName)
    }

    @Test
    fun `multiple phone numbers contact lookup outcome contains distinct labels`() {
        val multiContact = ContactRecord(
            contactId = "103",
            displayName = "Sarah Connor",
            numbers = listOf(
                PhoneNumberInfo("+15551111", "Mobile", isPrimary = true),
                PhoneNumberInfo("+15552222", "Home")
            )
        )
        val multiResult = ContactLookupResult.MultipleNumbers(multiContact)
        assertEquals(2, multiResult.contact.numbers.size)
        assertEquals("Mobile", multiResult.contact.numbers[0].typeLabel)
        assertEquals("Home", multiResult.contact.numbers[1].typeLabel)
    }

    @Test
    fun `call operation result handles telecom states and unsupported api levels`() {
        val success = CallOperationResult.Success("Answering call.")
        assertEquals("Answering call.", success.message)

        val notRinging = CallOperationResult.NotRinging
        assertTrue(notRinging is CallOperationResult)

        val unsupported = CallOperationResult.Unsupported("Requires Android 8.0 (API 26) or higher.")
        assertTrue(unsupported.reason.contains("Android 8.0"))

        val permReq = CallOperationResult.PermissionRequired("android.permission.ANSWER_PHONE_CALLS")
        assertEquals("android.permission.ANSWER_PHONE_CALLS", permReq.permission)
    }

    @Test
    fun `outgoing call outcomes distinguish direct call from dialer intent`() {
        val dialer = OutgoingCallOutcome.DialerOpened("Bob", "+15553333")
        assertEquals("Bob", dialer.targetName)
        assertEquals("+15553333", dialer.number)

        val direct = OutgoingCallOutcome.DirectCallPlaced("Bob", "+15553333")
        assertEquals("Bob", direct.targetName)

        val notFound = OutgoingCallOutcome.NotFound("Charlie")
        assertEquals("Charlie", notFound.query)

        val noNum = OutgoingCallOutcome.NoNumber("David")
        assertEquals("David", noNum.contactName)
    }

    @Test
    fun `incoming call info reflects ringing state and caller details`() {
        val ringingInfo = IncomingCallInfo(
            isRinging = true,
            incomingNumber = "+15559999",
            callerName = "Mom",
            state = 1
        )
        assertTrue(ringingInfo.isRinging)
        assertEquals("Mom", ringingInfo.callerName)
        assertEquals("+15559999", ringingInfo.incomingNumber)

        val idleInfo = IncomingCallInfo(
            isRinging = false,
            incomingNumber = null,
            callerName = null,
            state = 0
        )
        assertFalse(idleInfo.isRinging)
    }

    @Test
    fun `sms action result needs confirmation before dispatching`() {
        val confirmResult = ActionResult.needsConfirmation(
            spoken = "Do you want me to send this text to Alex: \"I'm running late\"?",
            actionId = "compose_sms",
            payload = mapOf(
                "recipient" to "Alex",
                "message" to "I'm running late",
                "direct_send" to false
            )
        )
        val json = confirmResult.toJsonObject()
        assertEquals("NEEDS_CONFIRMATION", json.getString("status"))
        assertTrue(json.getString("spoken_message").contains("Alex"))
        assertEquals("Alex", json.getJSONObject("data").getString("recipient"))
    }
}
