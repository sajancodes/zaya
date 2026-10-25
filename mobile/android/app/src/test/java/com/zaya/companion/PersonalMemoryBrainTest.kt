package com.zaya.companion

import com.zaya.companion.memory.MemoryCategory
import com.zaya.companion.memory.MemorySaveResult
import com.zaya.companion.memory.PersonalMemoryStore
import com.zaya.companion.memory.SensitiveDataDetector
import com.zaya.companion.runtime.ConversationalIntent
import com.zaya.companion.runtime.ConversationalResolver
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

class PersonalMemoryBrainTest {

    @Test
    fun `test 1 create approved structured memory across new categories`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_brain_test_1").toFile()
        val store = PersonalMemoryStore(tempDir)

        val res = store.remember(
            key = "active_project",
            value = "Building Zaya personal companion",
            category = MemoryCategory.PROJECT_GOAL,
            explicitConsent = true,
            sourceProvenance = "user_direct",
            importance = 0.9f
        )

        assertTrue(res is MemorySaveResult.Saved)
        val memories = store.getAllMemories()
        assertEquals(1, memories.size)
        assertEquals(MemoryCategory.PROJECT_GOAL, memories[0].category)
        assertEquals("active_project", memories[0].key)
        assertEquals(0.9f, memories[0].importance, 0.01f)

        tempDir.deleteRecursively()
    }

    @Test
    fun `test 2 persistence across component restart`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_brain_test_2").toFile()
        val store1 = PersonalMemoryStore(tempDir)
        store1.remember("python_env", "3.12 venv", MemoryCategory.PREFERENCE, true)

        // Restart component pointing to same storage
        val store2 = PersonalMemoryStore(tempDir)
        val memories = store2.getRelevantMemories("python env")
        assertEquals(1, memories.size)
        assertEquals("python_env", memories[0].key)
        assertEquals("3.12 venv", memories[0].value)

        tempDir.deleteRecursively()
    }

    @Test
    fun `test 3 duplicate detection and conflict history preservation`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_brain_test_3").toFile()
        val store = PersonalMemoryStore(tempDir)

        store.remember("theme", "Dark mode", MemoryCategory.PREFERENCE, true)
        // Duplicate remember
        val resDup = store.remember("theme", "Dark mode", MemoryCategory.PREFERENCE, true)
        assertTrue(resDup is MemorySaveResult.Saved)
        assertEquals(1, store.getAllMemories().size)

        // Update value -> preserves previous value
        val resUpdate = store.remember("theme", "OLED pitch black", MemoryCategory.PREFERENCE, true)
        assertTrue(resUpdate is MemorySaveResult.Saved)
        val mem = store.getAllMemories().first()
        assertEquals("OLED pitch black", mem.value)
        assertEquals(1, mem.previousValues.size)
        assertEquals("Dark mode", mem.previousValues[0])

        tempDir.deleteRecursively()
    }

    @Test
    fun `test 4 sensitive data filtering blocks secrets`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_brain_test_4").toFile()
        val store = PersonalMemoryStore(tempDir)

        val res1 = store.remember("admin_pwd", "MyPass1234!", MemoryCategory.PREFERENCE, true)
        assertTrue(res1 is MemorySaveResult.SensitiveDataBlocked)

        val res2 = store.remember("gps", "latitude: 27.717245 longitude: 85.323960", MemoryCategory.FACT, true)
        assertTrue(res2 is MemorySaveResult.SensitiveDataBlocked)

        val res3 = store.remember("health", "patient medical record diagnosis", MemoryCategory.FACT, true)
        assertTrue(res3 is MemorySaveResult.SensitiveDataBlocked)

        assertEquals(0, store.getAllMemories().size)
        tempDir.deleteRecursively()
    }

    @Test
    fun `test 5 memory exclusion when user asks to stop using`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_brain_test_5").toFile()
        val store = PersonalMemoryStore(tempDir)

        store.remember("work_city", "Kathmandu", MemoryCategory.FACT, true)
        assertEquals(1, store.getRelevantMemories("work city").size)

        val deactivated = store.deactivateMemory("work_city")
        assertTrue(deactivated)

        // Excluded from query results and prompt assembly
        assertEquals(0, store.getRelevantMemories("work city").size)
        val context = store.assembleContext("work city")
        assertEquals("", context)

        tempDir.deleteRecursively()
    }

    @Test
    fun `test 6 expiration cleanup`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_brain_test_6").toFile()
        val store = PersonalMemoryStore(tempDir)

        val past = System.currentTimeMillis() - 60_000
        val future = System.currentTimeMillis() + 3_600_000

        store.remember("parking_ticket", "Section C", MemoryCategory.FACT, true, expiresAt = past)
        store.remember("hotel_room", "Room 402", MemoryCategory.FACT, true, expiresAt = future)

        val expired = store.getRelevantMemories("parking ticket")
        assertEquals(0, expired.size)

        val active = store.getRelevantMemories("hotel room")
        assertEquals(1, active.size)
        assertEquals("hotel_room", active[0].key)

        tempDir.deleteRecursively()
    }

    @Test
    fun `test 7 database corruption recovery from backup`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_brain_test_7").toFile()
        val store1 = PersonalMemoryStore(tempDir)
        store1.remember("critical_fact", "Always available", MemoryCategory.FACT, true)

        // Corrupt main JSON file
        val jsonFile = File(tempDir, "personal_memory.json")
        jsonFile.writeText("{corrupted_data_not_json:")

        // New store instance should recover from backup
        val store2 = PersonalMemoryStore(tempDir)
        val recovered = store2.getRelevantMemories("critical fact")
        assertEquals(1, recovered.size)
        assertEquals("critical_fact", recovered[0].key)

        tempDir.deleteRecursively()
    }

    @Test
    fun `test 8 conversational memory intent resolution`() {
        val intent1 = ConversationalResolver.resolve(
            rawInput = "Remember this preference: always speak concisely",
            chatHistory = emptyList()
        )
        assertTrue(intent1 is ConversationalIntent.Remember)
        assertEquals("always speak concisely", (intent1 as ConversationalIntent.Remember).content)

        val intent2 = ConversationalResolver.resolve(
            rawInput = "What do you remember about my active project?",
            chatHistory = emptyList()
        )
        assertTrue(intent2 is ConversationalIntent.QueryMemory)
        assertEquals("my active project?", (intent2 as ConversationalIntent.QueryMemory).query)

        val intent3 = ConversationalResolver.resolve(
            rawInput = "Stop using this information",
            chatHistory = emptyList()
        )
        assertTrue(intent3 is ConversationalIntent.StopUsingMemory)

        val intent4 = ConversationalResolver.resolve(
            rawInput = "Clear my saved memories",
            chatHistory = emptyList()
        )
        assertTrue(intent4 is ConversationalIntent.ClearMemories)
        assertTrue((intent4 as ConversationalIntent.ClearMemories).requiresConfirmation)
    }
}
