package com.zaya.companion.memory

import android.content.Context
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.Locale
import java.util.UUID
import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

/**
 * Categories of user preferences and non-sensitive personal memories.
 */
enum class MemoryCategory(val displayName: String) {
    STYLE("Response Style"),
    ALIAS("App Aliases"),
    ROUTINE("Workflow Routines"),
    PREFERENCE("Preferences"),
    CORRECTION("Behavior Corrections");

    companion object {
        fun fromString(value: String): MemoryCategory {
            return when (value.uppercase(Locale.ROOT).trim()) {
                "STYLE" -> STYLE
                "ALIAS" -> ALIAS
                "ROUTINE" -> ROUTINE
                "CORRECTION" -> CORRECTION
                else -> PREFERENCE
            }
        }
    }
}

/**
 * An individual, non-sensitive, confirmed memory entry.
 */
data class PersonalMemory(
    val id: String = UUID.randomUUID().toString(),
    val category: MemoryCategory,
    val key: String,
    val value: String,
    val confirmed: Boolean = true,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
) {
    fun toJsonObject(): JSONObject = JSONObject().apply {
        put("id", id)
        put("category", category.name)
        put("key", key)
        put("value", value)
        put("confirmed", confirmed)
        put("created_at", createdAt)
        put("updated_at", updatedAt)
    }

    companion object {
        fun fromJsonObject(json: JSONObject): PersonalMemory {
            return PersonalMemory(
                id = json.optString("id", UUID.randomUUID().toString()),
                category = MemoryCategory.fromString(json.optString("category", "PREFERENCE")),
                key = json.optString("key", "").trim(),
                value = json.optString("value", "").trim(),
                confirmed = json.optBoolean("confirmed", true),
                createdAt = json.optLong("created_at", System.currentTimeMillis()),
                updatedAt = json.optLong("updated_at", System.currentTimeMillis()),
            )
        }
    }
}

/**
 * Result of attempting to save a personal memory entry.
 */
sealed class MemorySaveResult {
    data class Saved(val memory: PersonalMemory, val message: String) : MemorySaveResult()
    data class RequiresConfirmation(val key: String, val value: String, val category: MemoryCategory, val prompt: String) : MemorySaveResult()
    data class SensitiveDataBlocked(val reason: String) : MemorySaveResult()
    data class Invalid(val reason: String) : MemorySaveResult()
}

/**
 * Guard against storing sensitive information such as credentials, secrets, and private tokens.
 */
object SensitiveDataDetector {

    private val SENSITIVE_PATTERNS = listOf(
        Regex("(?i)\\b(password|passwd|pwd|passcode|pin\\s*code)\\b"),
        Regex("(?i)\\b(api[_-]?key|secret[_-]?key|auth[_-]?token|bearer\\s+[a-zA-Z0-9_.-]+)\\b"),
        Regex("(?i)\\b(credit\\s*card|debit\\s*card|cvv|cvc|card\\s*number)\\b"),
        Regex("\\b\\d{4}[- ]?\\d{4}[- ]?\\d{4}[- ]?\\d{4}\\b"), // Card pattern
        Regex("(?i)\\b(otp|one[ -]time[ -]password|verification[ -]code)\\b"),
        Regex("(?i)\\b(bank\\s*account|routing\\s*number|iban|swift\\s*code)\\b"),
        Regex("(?i)\\b(ssn|social\\s*security)\\b"),
        Regex("(?i)\\b(private\\s*key|ssh[_-]rsa|BEGIN\\s+(?:RSA\\s+)?PRIVATE\\s+KEY)\\b")
    )

    fun containsSensitiveData(text: String): Pair<Boolean, String?> {
        for (pattern in SENSITIVE_PATTERNS) {
            if (pattern.containsMatchIn(text)) {
                return true to "Content appears to contain sensitive security credentials, authentication codes, or financial information."
            }
        }
        return false to null
    }
}

/**
 * Privacy-conscious local personal memory store on the Android device.
 * Stores non-sensitive preferences, app aliases, assistant style, and routines in internal storage.
 * Completely separate from ephemeral task state and remote conversation history.
 */
class PersonalMemoryStore(
    private val context: Context,
    private val storageDir: File = File(context.filesDir, "memory")
) {
    companion object {
        private const val TAG = "PersonalMemoryStore"
        private const val FILE_NAME = "personal_memory.json"
        const val MAX_MEMORIES = 100
        const val MAX_KEY_LENGTH = 80
        const val MAX_VALUE_LENGTH = 300
    }

    private val lock = ReentrantLock()
    private val memoryFile: File get() = File(storageDir, FILE_NAME)
    private val _memories = MutableStateFlow<List<PersonalMemory>>(emptyList())
    val memories: StateFlow<List<PersonalMemory>> = _memories.asStateFlow()

    init {
        loadFromDisk()
    }

    /**
     * Attempts to save a new memory or update an existing one.
     * Enforces sensitive data filtering and confirmation requirements.
     */
    fun saveMemory(
        key: String,
        value: String,
        category: MemoryCategory = MemoryCategory.PREFERENCE,
        confirmed: Boolean = false
    ): MemorySaveResult {
        val cleanKey = key.trim().take(MAX_KEY_LENGTH)
        val cleanValue = value.trim().take(MAX_VALUE_LENGTH)

        if (cleanKey.isBlank() || cleanValue.isBlank()) {
            return MemorySaveResult.Invalid("Memory key and value cannot be empty.")
        }

        // 1. Strict Privacy & Security Check
        val (isSensitiveKey, reasonKey) = SensitiveDataDetector.containsSensitiveData(cleanKey)
        if (isSensitiveKey) {
            Log.w(TAG, "Blocked saving sensitive memory key: $reasonKey")
            return MemorySaveResult.SensitiveDataBlocked(reasonKey ?: "Sensitive information blocked.")
        }

        val (isSensitiveVal, reasonVal) = SensitiveDataDetector.containsSensitiveData(cleanValue)
        if (isSensitiveVal) {
            Log.w(TAG, "Blocked saving sensitive memory value: $reasonVal")
            return MemorySaveResult.SensitiveDataBlocked(reasonVal ?: "Sensitive information blocked.")
        }

        // 2. Ambiguity / Confirmation Gate
        if (!confirmed) {
            val prompt = "Would you like me to remember this preference? Category: ${category.displayName}, \"$cleanKey\" = \"$cleanValue\"."
            return MemorySaveResult.RequiresConfirmation(
                key = cleanKey,
                value = cleanValue,
                category = category,
                prompt = prompt
            )
        }

        // 3. Persist memory entry
        lock.withLock {
            val currentList = _memories.value.toMutableList()
            val existingIndex = currentList.indexOfFirst {
                it.category == category && it.key.equals(cleanKey, ignoreCase = true)
            }

            val now = System.currentTimeMillis()
            val savedEntry: PersonalMemory

            if (existingIndex >= 0) {
                savedEntry = currentList[existingIndex].copy(
                    value = cleanValue,
                    confirmed = true,
                    updatedAt = now
                )
                currentList[existingIndex] = savedEntry
            } else {
                if (currentList.size >= MAX_MEMORIES) {
                    // Remove oldest unpinned memory
                    currentList.sortBy { it.updatedAt }
                    currentList.removeAt(0)
                }
                savedEntry = PersonalMemory(
                    category = category,
                    key = cleanKey,
                    value = cleanValue,
                    confirmed = true,
                    createdAt = now,
                    updatedAt = now
                )
                currentList.add(0, savedEntry)
            }

            _memories.value = currentList.sortedByDescending { it.updatedAt }
            saveToDisk()

            Log.d(TAG, "Saved personal memory entry [${category.name}].")
            return MemorySaveResult.Saved(savedEntry, "Remembered: ${savedEntry.key} = \"${savedEntry.value}\".")
        }
    }

    /**
     * Removes an entry immediately from active memory and disk.
     * Guarantees it cannot be silently restored from stale context.
     */
    fun forgetMemory(key: String, category: MemoryCategory? = null): Boolean {
        val cleanKey = key.trim().lowercase(Locale.ROOT)
        if (cleanKey.isBlank()) return false

        lock.withLock {
            val currentList = _memories.value.toMutableList()
            val removed = currentList.removeAll { entry ->
                val matchesCat = category == null || entry.category == category
                matchesCat && (entry.key.lowercase(Locale.ROOT) == cleanKey || entry.key.lowercase(Locale.ROOT).contains(cleanKey))
            }

            if (removed) {
                _memories.value = currentList
                saveToDisk()
                Log.d(TAG, "Forgotten personal memory matching requested key.")
                return true
            }
            return false
        }
    }

    /**
     * Deletes a specific memory entry by its ID.
     */
    fun deleteMemoryById(id: String): Boolean {
        lock.withLock {
            val currentList = _memories.value.toMutableList()
            val removed = currentList.removeAll { it.id == id }
            if (removed) {
                _memories.value = currentList
                saveToDisk()
                return true
            }
            return false
        }
    }

    /**
     * Completely clears all personal memories.
     */
    fun clearAll(): Boolean {
        lock.withLock {
            _memories.value = emptyList()
            if (memoryFile.exists()) {
                memoryFile.delete()
            }
            return true
        }
    }

    /**
     * Retrieves relevant memories matching the given user query.
     * Returns ONLY items with lexical relevance to prevent leaking unrelated facts.
     */
    fun getRelevantMemories(query: String, limit: Int = 5): List<PersonalMemory> {
        val clean = query.lowercase(Locale.ROOT).trim()
        if (clean.isBlank()) return emptyList()

        val tokens = clean.split("[^a-zA-Z0-9]+".toRegex()).filter { it.length > 2 }
        if (tokens.isEmpty()) return emptyList()

        val all = _memories.value
        val scored = mutableListOf<Pair<Int, PersonalMemory>>()

        for (entry in all) {
            val hayKey = entry.key.lowercase(Locale.ROOT)
            val hayVal = entry.value.lowercase(Locale.ROOT)
            val hayCat = entry.category.name.lowercase(Locale.ROOT)

            var score = 0
            for (token in tokens) {
                if (hayKey == token) score += 10
                else if (hayKey.contains(token)) score += 6

                if (hayVal.contains(token)) score += 3
                if (hayCat.contains(token)) score += 1
            }

            if (score > 0) {
                scored.add(score to entry)
            }
        }

        return scored.sortedByDescending { it.first }.map { it.second }.take(limit)
    }

    /**
     * Look up a configured app alias (e.g. "camera" -> "opencamera", "music" -> "spotify").
     */
    fun getAppAlias(aliasName: String): String? {
        val clean = aliasName.lowercase(Locale.ROOT).trim()
        val entry = _memories.value.firstOrNull {
            it.category == MemoryCategory.ALIAS && it.key.lowercase(Locale.ROOT) == clean
        }
        return entry?.value
    }

    /**
     * Returns assistant response style instructions if configured.
     */
    fun getAssistantStylePreference(): String? {
        val entry = _memories.value.firstOrNull { it.category == MemoryCategory.STYLE }
        return entry?.value
    }

    // ── Persistence ──────────────────────────────────────────────────────────

    private fun loadFromDisk() {
        lock.withLock {
            if (!memoryFile.exists()) {
                _memories.value = emptyList()
                return
            }

            try {
                val content = memoryFile.readText(Charsets.UTF_8)
                val jsonArr = JSONArray(content)
                val list = mutableListOf<PersonalMemory>()

                for (i in 0 until jsonArr.length()) {
                    val obj = jsonArr.optJSONObject(i) ?: continue
                    list.add(PersonalMemory.fromJsonObject(obj))
                }

                _memories.value = list.sortedByDescending { it.updatedAt }
                Log.i(TAG, "Loaded ${_memories.value.size} personal memories from local storage.")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to load personal memories from disk: ${e.message}")
                _memories.value = emptyList()
            }
        }
    }

    private fun saveToDisk() {
        try {
            if (!storageDir.exists()) {
                storageDir.mkdirs()
            }
            val arr = JSONArray()
            _memories.value.forEach { arr.put(it.toJsonObject()) }

            val tempFile = File(storageDir, "$FILE_NAME.tmp")
            tempFile.writeText(arr.toString(2), Charsets.UTF_8)
            if (tempFile.renameTo(memoryFile)) {
                Log.d(TAG, "Saved ${_memories.value.size} memories to disk.")
            } else {
                memoryFile.writeText(arr.toString(2), Charsets.UTF_8)
                tempFile.delete()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error writing personal memories to disk: ${e.message}")
        }
    }
}
