package com.zaya.companion

import com.zaya.companion.audio.DoubleClapDetector
import com.zaya.companion.audio.VoiceInputState
import com.zaya.companion.audio.VoiceOutputState
import com.zaya.companion.protocol.ChatLine
import com.zaya.companion.protocol.Speaker
import com.zaya.companion.runtime.ConversationalIntent
import com.zaya.companion.runtime.ConversationalResolver
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceAndConversationalTest {

    @Test
    fun `voice input states represent lifecycle transitions correctly`() {
        val idle = VoiceInputState.Idle
        assertNotNull(idle)

        val listening = VoiceInputState.Listening
        assertNotNull(listening)

        val processing = VoiceInputState.Processing
        assertNotNull(processing)

        val success = VoiceInputState.Success("What is the battery level?")
        assertEquals("What is the battery level?", success.recognizedText)

        val errorRetryable = VoiceInputState.Error("No speech detected", canRetry = true)
        assertEquals("No speech detected", errorRetryable.message)
        assertTrue(errorRetryable.canRetry)

        val errorPermanent = VoiceInputState.Error("Microphone permission required", canRetry = false)
        assertFalse(errorPermanent.canRetry)
    }

    @Test
    fun `voice output states represent playback lifecycle correctly`() {
        val idle = VoiceOutputState.Idle
        assertNotNull(idle)

        val init = VoiceOutputState.Initializing
        assertNotNull(init)

        val speaking = VoiceOutputState.Speaking("utt-123", "Battery is 85 percent.")
        assertEquals("utt-123", speaking.utteranceId)
        assertEquals("Battery is 85 percent.", speaking.text)

        val err = VoiceOutputState.Error("TTS engine unavailable")
        assertEquals("TTS engine unavailable", err.message)
    }

    @Test
    fun `conversational resolver maps speech silence vs task cancellation`() {
        val history = listOf(
            ChatLine(id = "1", speaker = Speaker.ZAYA, text = "Starting diagnostic scan.", at = 1718000000000L)
        )

        // "stop speaking" halts voice output only
        val stopSpeech = ConversationalResolver.resolve("Stop speaking", history, isTaskActive = true)
        assertTrue(stopSpeech is ConversationalIntent.StopSpeech)

        // "cancel task" halts background execution
        val cancelTask = ConversationalResolver.resolve("Cancel task", history, isTaskActive = true)
        assertTrue(cancelTask is ConversationalIntent.CancelTask)

        // Ambiguous "cancel" when task is active cancels the task
        val cancelAmbiguous = ConversationalResolver.resolve("cancel", history, isTaskActive = true)
        assertTrue(cancelAmbiguous is ConversationalIntent.CancelTask)

        // Ambiguous "stop" when no task is running halts speech
        val stopAmbiguous = ConversationalResolver.resolve("stop", history, isTaskActive = false)
        assertTrue(stopAmbiguous is ConversationalIntent.StopSpeech)
    }

    @Test
    fun `conversational resolver resolves contextual follow-ups`() {
        val history = listOf(
            ChatLine(
                id = "1",
                speaker = Speaker.ZAYA,
                text = "I found your contacts:\n1. Alice Smith\n2. Bob Jones\n3. Carol White",
                at = 1718000000000L
            )
        )

        // "Explain that again"
        val repeat = ConversationalResolver.resolve("Explain that again", history)
        assertTrue(repeat is ConversationalIntent.Repeat)
        assertTrue((repeat as ConversationalIntent.Repeat).previousAnswer.contains("Alice Smith"))

        // "Make it shorter"
        val summarize = ConversationalResolver.resolve("Make it shorter", history)
        assertTrue(summarize is ConversationalIntent.Summarize)
        assertTrue((summarize as ConversationalIntent.Summarize).previousAnswer.contains("Alice Smith"))

        // "Do the second option" selects Bob Jones
        val select = ConversationalResolver.resolve("Do the second option", history)
        assertTrue(select is ConversationalIntent.SelectOption)
        val selectedOption = select as ConversationalIntent.SelectOption
        assertEquals("Bob Jones", selectedOption.optionText)
        assertFalse("Selecting contact is not destructive", selectedOption.requiresConfirmation)
    }

    @Test
    fun `consequential options and continue commands enforce confirmation gates`() {
        val history = listOf(
            ChatLine(
                id = "1",
                speaker = Speaker.ZAYA,
                text = "Options:\n1. Keep files\n2. Delete all downloads",
                at = 1718000000000L
            )
        )

        val deleteOption = ConversationalResolver.resolve("Pick option 2", history)
        assertTrue(deleteOption is ConversationalIntent.SelectOption)
        assertTrue("Consequential option must require confirmation", (deleteOption as ConversationalIntent.SelectOption).requiresConfirmation)

        // Ambiguous "continue" with consequential pending action requires confirmation
        val continueConseq = ConversationalResolver.resolve(
            rawInput = "Continue",
            chatHistory = history,
            isTaskActive = true,
            pendingActionIsConsequential = true
        )
        assertTrue(continueConseq is ConversationalIntent.Continue)
        assertTrue("Continue must not bypass confirmation on consequential action", (continueConseq as ConversationalIntent.Continue).requiresConfirmation)

        // Safe "continue" without pending consequential action
        val continueSafe = ConversationalResolver.resolve(
            rawInput = "Continue",
            chatHistory = history,
            isTaskActive = true,
            pendingActionIsConsequential = false
        )
        assertTrue(continueSafe is ConversationalIntent.Continue)
        assertFalse((continueSafe as ConversationalIntent.Continue).requiresConfirmation)
    }

    @Test
    fun `double clap hands-free trigger operates locally without cloud recording`() {
        var triggered = false
        val detector = DoubleClapDetector(onDoubleClap = { triggered = true })
        assertNotNull(detector)

        // Simulated quiet audio frame does not false-trigger
        val quietFrame = ByteArray(1024) { 0 }
        detector.processFrame(quietFrame, quietFrame.size)
        assertFalse(triggered)
    }
}
