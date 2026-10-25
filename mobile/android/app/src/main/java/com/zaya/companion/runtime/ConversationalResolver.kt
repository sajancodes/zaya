package com.zaya.companion.runtime

import com.zaya.companion.protocol.ChatLine
import com.zaya.companion.protocol.Speaker
import java.util.Locale

sealed class ConversationalIntent {
    data class Normal(val text: String) : ConversationalIntent()
    data object StopSpeech : ConversationalIntent()
    data class CancelTask(val reason: String = "Cancelled by user voice command") : ConversationalIntent()
    data class Repeat(val previousAnswer: String) : ConversationalIntent()
    data class Summarize(val previousAnswer: String) : ConversationalIntent()
    data class SelectOption(val optionText: String, val requiresConfirmation: Boolean) : ConversationalIntent()
    data class Continue(val requiresConfirmation: Boolean) : ConversationalIntent()
    data class Remember(val content: String) : ConversationalIntent()
    data class QueryMemory(val query: String) : ConversationalIntent()
    data class ForgetMemory(val target: String) : ConversationalIntent()
    data class StopUsingMemory(val target: String) : ConversationalIntent()
    data class ClearMemories(val requiresConfirmation: Boolean = true) : ConversationalIntent()
}

/**
 * Resolves context-aware conversational follow-ups and distinguishes audio cancellation,
 * task cancellation, and memory consent operations.
 */
object ConversationalResolver {

    private val STOP_SPEECH_WORDS = setOf(
        "stop speaking", "be quiet", "silence", "stop talking", "shut up", "mute"
    )

    private val CANCEL_TASK_WORDS = setOf(
        "cancel task", "stop task", "abort task", "cancel running task", "stop the task"
    )

    fun resolve(
        rawInput: String,
        chatHistory: List<ChatLine>,
        isTaskActive: Boolean = false,
        pendingActionIsConsequential: Boolean = false
    ): ConversationalIntent {
        val clean = rawInput.trim()
        val lower = clean.lowercase(Locale.ROOT)

        // 1. Explicit speech stop
        if (lower in STOP_SPEECH_WORDS) {
            return ConversationalIntent.StopSpeech
        }

        // 2. Explicit task cancellation
        if (lower in CANCEL_TASK_WORDS) {
            return ConversationalIntent.CancelTask()
        }

        // 3. Ambiguous "stop" or "cancel"
        if (lower in setOf("cancel", "stop", "abort")) {
            return if (isTaskActive) {
                ConversationalIntent.CancelTask()
            } else {
                ConversationalIntent.StopSpeech
            }
        }

        // 4. Memory Intent Operations
        if (lower.startsWith("remember this preference") || lower.startsWith("remember that") || lower.startsWith("remember to") || lower.startsWith("remember ")) {
            val content = clean.replaceFirst(Regex("(?i)^remember\\s+(?:this\\s+preference[:\\s]*|that\\s+|to\\s+)?"), "").trim()
            if (content.isNotBlank()) {
                return ConversationalIntent.Remember(content)
            }
        }

        if (lower.startsWith("what do you remember") || lower.startsWith("tell me what you remember")) {
            val query = clean.replaceFirst(Regex("(?i)^(?:what\\s+do\\s+you\\s+remember|tell\\s+me\\s+what\\s+you\\s+remember)\\s*(?:about\\s+)?"), "").trim()
            return ConversationalIntent.QueryMemory(query)
        }

        if (lower in setOf("do not remember this", "don't remember this", "do not remember that", "don't remember that", "forget this")) {
            return ConversationalIntent.ForgetMemory("current_turn")
        }

        if (lower.startsWith("stop using this information") || lower.startsWith("stop using that") || lower.startsWith("stop using ")) {
            val target = clean.replaceFirst(Regex("(?i)^stop\\s+using\\s+(?:this\\s+information|that|this)?\\s*"), "").trim()
            return ConversationalIntent.StopUsingMemory(target.ifBlank { "current_topic" })
        }

        if (lower in setOf("clear my saved memories", "clear saved memories", "clear all memories", "wipe my memories")) {
            return ConversationalIntent.ClearMemories(requiresConfirmation = true)
        }

        val lastZayaLine = chatHistory.lastOrNull { it.speaker == Speaker.ZAYA }?.text

        // 5. "Explain that again" / "Repeat"
        if (lower in setOf("explain that again", "explain again", "say that again", "repeat that", "what did you say", "repeat")) {
            return if (!lastZayaLine.isNullOrBlank()) {
                ConversationalIntent.Repeat(lastZayaLine)
            } else {
                ConversationalIntent.Normal(clean)
            }
        }

        // 6. "Make it shorter" / "Summarize"
        if (lower in setOf("make it shorter", "summarize that", "shorter please", "too long", "give me the short version", "tldr")) {
            return if (!lastZayaLine.isNullOrBlank()) {
                ConversationalIntent.Summarize(lastZayaLine)
            } else {
                ConversationalIntent.Normal(clean)
            }
        }

        // 7. Numbered / Ordinal option selection ("first option", "second option", "option 2")
        val optionMatch = Regex("(?i)\\b(?:do|pick|choose|select|take)?\\s*(?:the\\s+)?(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|option\\s+[1-5]|[1-5])(?:\\s+option)?\\b")
            .find(lower)

        if (optionMatch != null && !lastZayaLine.isNullOrBlank()) {
            val options = extractOptions(lastZayaLine)
            val ordStr = optionMatch.groupValues[1].replace("option", "").trim()
            val index = ordinalToIndex(ordStr)

            if (index in options.indices) {
                val selected = options[index]
                val consequential = isConsequentialText(selected)
                return ConversationalIntent.SelectOption(selected, requiresConfirmation = consequential)
            }
        }

        // 8. "Continue" / "Go ahead"
        if (lower in setOf("continue", "go ahead", "proceed", "yes continue")) {
            return ConversationalIntent.Continue(requiresConfirmation = pendingActionIsConsequential)
        }

        return ConversationalIntent.Normal(clean)
    }

    private fun ordinalToIndex(s: String): Int {
        return when (s.lowercase(Locale.ROOT)) {
            "first", "1st", "1" -> 0
            "second", "2nd", "2" -> 1
            "third", "3rd", "3" -> 2
            "fourth", "4th", "4" -> 3
            "fifth", "5th", "5" -> 4
            else -> -1
        }
    }

    private fun extractOptions(text: String): List<String> {
        val list = mutableListOf<String>()
        for (line in text.lines()) {
            val trimmed = line.trim()
            val match = Regex("^(?:[0-9]+[.)]|[-*•])\\s+(.+)$").find(trimmed)
            if (match != null) {
                list.add(match.groupValues[1].trim())
            }
        }
        return list
    }

    private fun isConsequentialText(text: String): Boolean {
        val words = text.lowercase(Locale.ROOT).split(Regex("\\s+"))
        return words.any { it in setOf("delete", "remove", "pay", "purchase", "send", "transfer", "wipe", "format", "confirm") }
    }
}
