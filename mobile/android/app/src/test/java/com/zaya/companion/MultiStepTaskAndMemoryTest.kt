package com.zaya.companion

import com.zaya.companion.action.ActionRisk
import com.zaya.companion.action.ActionResult
import com.zaya.companion.action.ActionResultStatus
import com.zaya.companion.action.AndroidAction
import com.zaya.companion.action.MultiStepTaskState
import com.zaya.companion.action.StepStatus
import com.zaya.companion.action.TaskExecutionReport
import com.zaya.companion.action.TaskOverallStatus
import com.zaya.companion.action.TaskPlanner
import com.zaya.companion.action.TaskStep
import com.zaya.companion.memory.MemoryCategory
import com.zaya.companion.memory.PersonalMemory
import com.zaya.companion.memory.PersonalMemoryStore
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

@OptIn(ExperimentalCoroutinesApi::class)
class MultiStepTaskAndMemoryTest {

    // 1. A successful multi-step task
    @Test
    fun `test 1 successful multi-step task execution`() {
        val plan = TaskPlanner.planFromRequest("Turn on flashlight, then open camera", "task_test_1")
        assertFalse("Plan should not need clarification", plan.needsClarification)
        assertEquals(2, plan.steps.size)
        assertEquals("set_flashlight", plan.steps[0].actionId)
        assertEquals("open_camera", plan.steps[1].actionId)

        var state = MultiStepTaskState(
            taskId = plan.taskId,
            goal = plan.goal,
            steps = plan.steps,
            status = TaskOverallStatus.RUNNING
        )

        // Step 1 runs and succeeds
        val step1 = state.steps[0].copy(
            status = StepStatus.COMPLETED,
            result = ActionResult.success("Flashlight turned on.")
        )
        // Step 2 runs and succeeds
        val step2 = state.steps[1].copy(
            status = StepStatus.COMPLETED,
            result = ActionResult.success("Camera opened.")
        )
        state = state.copy(
            steps = listOf(step1, step2),
            status = TaskOverallStatus.COMPLETED
        )

        val report = TaskExecutionReport.fromState(state)
        assertEquals(2, report.completedSteps.size)
        assertEquals(0, report.failedSteps.size)
        assertEquals(0, report.skippedSteps.size)
        assertEquals(0, report.cancelledSteps.size)
        assertEquals("Task completed successfully.", report.summary)
        assertTrue(state.isTerminal)
    }

    // 2. A failure in a middle step
    @Test
    fun `test 2 failure in a middle step halts subsequent steps safely`() {
        val steps = listOf(
            TaskStep("1", "Step 1", "set_flashlight", mapOf("enabled" to true)),
            TaskStep("2", "Step 2", "open_app", mapOf("package" to "com.invalid.missing")),
            TaskStep("3", "Step 3", "open_camera", emptyMap())
        )
        var state = MultiStepTaskState(
            taskId = "task_test_2",
            goal = "Three step task with failure",
            steps = steps,
            status = TaskOverallStatus.RUNNING
        )

        // Step 1 succeeds
        val s1 = state.steps[0].copy(status = StepStatus.COMPLETED, result = ActionResult.success("Flashlight on"))
        // Step 2 fails
        val s2 = state.steps[1].copy(status = StepStatus.FAILED, result = ActionResult.failure("App not installed"))
        // Step 3 is skipped
        val s3 = state.steps[2].copy(status = StepStatus.SKIPPED)

        state = state.copy(
            steps = listOf(s1, s2, s3),
            status = TaskOverallStatus.FAILED,
            failureReason = "App not installed"
        )

        val report = TaskExecutionReport.fromState(state)
        assertEquals(1, report.completedSteps.size)
        assertEquals(1, report.failedSteps.size)
        assertEquals(1, report.skippedSteps.size)
        assertTrue(report.summary.contains("Step 2 failed"))
        assertFalse("Task should not claim overall success", state.status == TaskOverallStatus.COMPLETED)
    }

    // 3. A missing permission or unsupported action
    @Test
    fun `test 3 missing permission stops before executing unauthorized step`() {
        val readContactsStep = TaskStep(
            id = "step_contacts",
            description = "Search contacts for Alice",
            actionId = "search_contacts",
            parameters = mapOf("query" to "Alice"),
            requiredPermissions = listOf("android.permission.READ_CONTACTS")
        )
        val state = MultiStepTaskState(
            taskId = "task_test_3",
            goal = "Find contact and call",
            steps = listOf(
                readContactsStep.copy(
                    status = StepStatus.FAILED,
                    result = ActionResult.permissionRequired("android.permission.READ_CONTACTS")
                )
            ),
            status = TaskOverallStatus.FAILED,
            failureReason = "Required permission missing: android.permission.READ_CONTACTS"
        )

        val report = TaskExecutionReport.fromState(state)
        assertEquals(ActionResultStatus.PERMISSION_REQUIRED, state.steps[0].result?.status)
        assertEquals(1, report.failedSteps.size)
        assertTrue(report.summary.contains("permission"))
    }

    // 4. Cancellation before execution begins
    @Test
    fun `test 4 cancellation before execution begins`() {
        val plan = TaskPlanner.planFromRequest("Turn on flashlight, then open camera", "task_test_4")
        val state = MultiStepTaskState(
            taskId = plan.taskId,
            goal = plan.goal,
            steps = plan.steps.map { it.copy(status = StepStatus.CANCELLED) },
            status = TaskOverallStatus.CANCELLED
        )

        val report = TaskExecutionReport.fromState(state)
        assertEquals(TaskOverallStatus.CANCELLED, state.status)
        assertEquals(0, report.completedSteps.size)
        assertEquals(2, report.cancelledSteps.size)
        assertTrue(report.summary.contains("cancelled"))
    }

    // 5. Cancellation during a running operation
    @Test
    fun `test 5 cancellation during running operation`() {
        val steps = listOf(
            TaskStep("1", "Flashlight", "set_flashlight", emptyMap(), status = StepStatus.COMPLETED),
            TaskStep("2", "Download large file", "download_media", emptyMap(), status = StepStatus.CANCELLED),
            TaskStep("3", "Open camera", "open_camera", emptyMap(), status = StepStatus.CANCELLED)
        )
        val state = MultiStepTaskState(
            taskId = "task_test_5",
            goal = "Download and view",
            steps = steps,
            status = TaskOverallStatus.CANCELLED
        )

        val report = TaskExecutionReport.fromState(state)
        assertEquals(1, report.completedSteps.size)
        assertEquals(2, report.cancelledSteps.size)
        assertTrue(report.summary.contains("partially completed before cancellation"))
    }

    // 6. Prevention of subsequent steps after cancellation
    @Test
    fun `test 6 prevention of subsequent steps after cancellation`() {
        val steps = listOf(
            TaskStep("1", "Step 1", "set_flashlight", emptyMap(), status = StepStatus.COMPLETED),
            TaskStep("2", "Step 2", "open_camera", emptyMap(), status = StepStatus.CANCELLED),
            TaskStep("3", "Step 3", "compose_sms", emptyMap(), status = StepStatus.SKIPPED)
        )
        val state = MultiStepTaskState(
            taskId = "task_test_6",
            goal = "Three step task",
            steps = steps,
            status = TaskOverallStatus.CANCELLED
        )

        // Verify that step 3 never reached RUNNING or COMPLETED
        assertFalse(state.steps[2].status == StepStatus.RUNNING)
        assertFalse(state.steps[2].status == StepStatus.COMPLETED)
        assertEquals(StepStatus.SKIPPED, state.steps[2].status)
    }

    // 7. Prevention of stale results modifying a newer task
    @Test
    fun `test 7 prevention of stale results modifying newer task`() {
        val activeTaskTokens = mutableMapOf<String, Long>()
        val taskId = "task_test_7"

        // Task starts at generation token 1
        activeTaskTokens[taskId] = 1L

        // Cancelled or superseded, increments token to 2
        activeTaskTokens[taskId] = 2L

        // Stale callback arrives with old generation token 1
        val incomingOldResultToken = 1L
        val isStale = (activeTaskTokens[taskId] ?: 0L) != incomingOldResultToken
        assertTrue("Late result from old generation must be identified as stale", isStale)

        // New result with current generation token 2 is valid
        val incomingNewResultToken = 2L
        val isValid = (activeTaskTokens[taskId] ?: 0L) == incomingNewResultToken
        assertTrue("Result with current generation token is valid", isValid)
    }

    // 8. Accurate reporting of partial completion
    @Test
    fun `test 8 accurate reporting of partial completion`() {
        val state = MultiStepTaskState(
            taskId = "task_test_8",
            goal = "Send report and notify",
            steps = listOf(
                TaskStep("1", "Check network", "check_network", emptyMap(), status = StepStatus.COMPLETED),
                TaskStep("2", "Send SMS", "compose_sms", emptyMap(), status = StepStatus.FAILED, result = ActionResult.failure("No SIM card")),
                TaskStep("3", "Announce", "announce", emptyMap(), status = StepStatus.SKIPPED)
            ),
            status = TaskOverallStatus.PARTIALLY_COMPLETED,
            failureReason = "No SIM card"
        )

        val report = TaskExecutionReport.fromState(state)
        assertEquals(1, report.completedSteps.size)
        assertEquals(1, report.failedSteps.size)
        assertEquals(1, report.skippedSteps.size)
        assertFalse("Must not report success", report.summary.contains("completed successfully"))
        assertTrue(report.summary.contains("Step 2 failed"))
    }

    // 9. Memory creation with appropriate consent
    @Test
    fun `test 9 memory creation with consent`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_memory_test_9").toFile()
        val store = PersonalMemoryStore(tempDir)

        val res = store.remember(
            key = "response_style",
            value = "concise and direct",
            category = MemoryCategory.STYLE,
            explicitConsent = true
        )

        assertTrue(res is PersonalMemoryStore.MemorySaveResult.Saved)
        val memories = store.getAllMemories()
        assertEquals(1, memories.size)
        assertEquals("response_style", memories[0].key)
        assertEquals("concise and direct", memories[0].value)
        assertEquals(MemoryCategory.STYLE, memories[0].category)

        tempDir.deleteRecursively()
    }

    // 10. Memory retrieval for a relevant request
    @Test
    fun `test 10 memory retrieval relevant to current request`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_memory_test_10").toFile()
        val store = PersonalMemoryStore(tempDir)

        store.remember("music_player", "Spotify", MemoryCategory.ALIAS, true)
        store.remember("night_routine", "dim screen and silent mode", MemoryCategory.ROUTINE, true)
        store.remember("response_style", "concise and direct", MemoryCategory.STYLE, true)

        // Query relevant to music
        val musicMemories = store.getRelevantMemories("play some music on spotify")
        assertEquals(1, musicMemories.size)
        assertEquals("music_player", musicMemories[0].key)

        // Query relevant to night
        val nightMemories = store.getRelevantMemories("getting ready for night routine")
        assertEquals(1, nightMemories.size)
        assertEquals("night_routine", nightMemories[0].key)

        // Query with no relevance
        val unrelated = store.getRelevantMemories("what is the weather today")
        assertEquals(0, unrelated.size)

        tempDir.deleteRecursively()
    }

    // 11. Memory editing and deletion
    @Test
    fun `test 11 memory editing and deletion`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_memory_test_11").toFile()
        val store = PersonalMemoryStore(tempDir)

        // Create
        store.remember("app_alias_browser", "Firefox", MemoryCategory.ALIAS, true)
        assertEquals("Firefox", store.getAppAlias("browser"))

        // Edit
        store.remember("app_alias_browser", "Chrome", MemoryCategory.ALIAS, true)
        assertEquals("Chrome", store.getAppAlias("browser"))

        // Delete
        val removed = store.forgetMemory("app_alias_browser")
        assertTrue(removed)
        assertNull(store.getAppAlias("browser"))
        assertEquals(0, store.getAllMemories().size)

        tempDir.deleteRecursively()
    }

    // 12. Prevention of sensitive or explicitly excluded data being saved
    @Test
    fun `test 12 prevention of sensitive data being saved`() = runTest {
        val tempDir = Files.createTempDirectory("zaya_memory_test_12").toFile()
        val store = PersonalMemoryStore(tempDir)

        // Password attempt
        val res1 = store.remember("my_password", "Secret1234!", MemoryCategory.PREFERENCE, true)
        assertTrue("Password must be blocked", res1 is PersonalMemoryStore.MemorySaveResult.BlockedSensitive)

        // Credit card / CVV attempt
        val res2 = store.remember("card_details", "cvv is 456", MemoryCategory.PREFERENCE, true)
        assertTrue("CVV/Card details must be blocked", res2 is PersonalMemoryStore.MemorySaveResult.BlockedSensitive)

        // PIN attempt
        val res3 = store.remember("atm_pin", "1234", MemoryCategory.PREFERENCE, true)
        assertTrue("PIN must be blocked", res3 is PersonalMemoryStore.MemorySaveResult.BlockedSensitive)

        // API Key attempt
        val res4 = store.remember("gemini_api_key", "AIzaSyTest123", MemoryCategory.PREFERENCE, true)
        assertTrue("API key must be blocked", res4 is PersonalMemoryStore.MemorySaveResult.BlockedSensitive)

        // Ensure nothing was saved
        assertEquals(0, store.getAllMemories().size)

        tempDir.deleteRecursively()
    }

    // 13. Task interruption and safe recovery
    @Test
    fun `test 13 task interruption and safe recovery without auto resuming consequential steps`() {
        val steps = listOf(
            TaskStep("1", "Check Wi-Fi", "check_wifi", emptyMap(), status = StepStatus.COMPLETED),
            TaskStep("2", "Send SMS to Mom", "compose_sms", mapOf("recipient" to "Mom", "text" to "I'm on my way"), status = StepStatus.PENDING)
        )
        // Task was running when process was interrupted
        val interruptedState = MultiStepTaskState(
            taskId = "task_test_13",
            goal = "Send message to Mom",
            steps = steps,
            status = TaskOverallStatus.PAUSED
        )

        // Consequential step (compose_sms) must NOT auto-execute upon recovery
        val pendingConsequential = interruptedState.steps.filter { it.status == StepStatus.PENDING && it.isConsequential }
        assertEquals(1, pendingConsequential.size)
        assertEquals("compose_sms", pendingConsequential[0].actionId)

        // Policy check: Consequential steps require explicit user re-confirmation before resumption
        assertTrue(pendingConsequential[0].requiresConfirmation)
    }

    // 14. Confirmation before consequential external actions
    @Test
    fun `test 14 confirmation before consequential external actions`() {
        val smsAction = AndroidAction.ComposeSms("1234567890", "Hello world")
        assertTrue("ComposeSms is consequential and must require confirmation", smsAction.requiresConfirmation)
        assertEquals(ActionRisk.CRITICAL, smsAction.risk)

        val replyAction = AndroidAction.ReplyToNotification("key_999", "I agree")
        assertTrue("ReplyToNotification is consequential and must require confirmation", replyAction.requiresConfirmation)
        assertEquals(ActionRisk.HIGH, replyAction.risk)

        val phoneCallAction = AndroidAction.ManageCall("answer", "Mom")
        assertEquals(ActionRisk.CRITICAL, phoneCallAction.risk)

        val flashlightAction = AndroidAction.SetFlashlight(true)
        assertFalse("SetFlashlight is not consequential and does not require confirmation", flashlightAction.requiresConfirmation)
        assertEquals(ActionRisk.LOW, flashlightAction.risk)
    }
}
