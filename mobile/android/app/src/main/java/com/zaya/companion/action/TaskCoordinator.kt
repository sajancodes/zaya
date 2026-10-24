package com.zaya.companion.action

import android.Manifest
import android.util.Log
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong

/**
 * Lifecycle status of an individual task step.
 */
enum class StepStatus {
    PENDING,
    RUNNING,
    COMPLETED,
    FAILED,
    SKIPPED,
    CANCELLED,
}

/**
 * Overall outcome status of a multi-step task coordinator execution.
 */
enum class TaskOverallStatus {
    NOT_STARTED,
    RUNNING,
    COMPLETED,
    PARTIALLY_COMPLETED,
    FAILED,
    CANCELLED,
    NEEDS_CONFIRMATION,
    CLARIFICATION_REQUIRED,
}

/**
 * Model representing an atomic step in a multi-step assistant task.
 */
data class TaskStep(
    val stepIndex: Int,
    val actionId: String,
    val description: String,
    val action: AndroidAction,
    var status: StepStatus = StepStatus.PENDING,
    var result: ActionResult? = null,
    val requiredPermissions: List<String> = emptyList(),
    val inputPipes: Map<String, String> = emptyMap(), // Maps output field from previous steps to argument
    val isConsequential: Boolean = false,
)

/**
 * Runtime state of a multi-step task.
 */
data class MultiStepTaskState(
    val taskId: String,
    val originalGoal: String,
    val steps: List<TaskStep>,
    val currentStepIndex: Int = 0,
    val overallStatus: TaskOverallStatus = TaskOverallStatus.NOT_STARTED,
    val isCancelled: Boolean = false,
    val cancellationReason: String? = null,
    val irreversibleActionsCompleted: List<String> = emptyList(),
    val clarificationQuestion: String? = null,
    val summary: String = "",
    val executionToken: Long = 0L,
) {
    val totalSteps: Int get() = steps.size
    val completedStepsCount: Int get() = steps.count { it.status == StepStatus.COMPLETED }
    val isRunning: Boolean get() = overallStatus == TaskOverallStatus.RUNNING
}

/**
 * Final execution report returned after task completion, failure, or cancellation.
 */
data class TaskExecutionReport(
    val taskId: String,
    val originalGoal: String,
    val totalSteps: Int,
    val completedSteps: Int,
    val failedSteps: Int,
    val skippedSteps: Int,
    val cancelledSteps: Int,
    val status: TaskOverallStatus,
    val summary: String,
    val stepDetails: List<TaskStep>,
    val clarificationQuestion: String? = null,
    val irreversibleNote: String? = null,
    val data: Map<String, Any?> = emptyMap(),
)

/**
 * Decomposes natural language requests or structured intents into validated steps.
 */
object TaskPlanner {

    fun planFromRequest(request: String, registry: ActionRegistry): Pair<List<TaskStep>, String?> {
        val clean = request.trim()
        val steps = mutableListOf<TaskStep>()

        val lower = clean.lowercase()

        // 1. "Turn on the flashlight, then open my camera"
        if (lower.contains("flashlight") && (lower.contains("then") || lower.contains("and")) && lower.contains("camera")) {
            steps.add(
                TaskStep(
                    stepIndex = 1,
                    actionId = "set_flashlight",
                    description = "Turn on the flashlight",
                    action = AndroidAction.SetFlashlight(true),
                    requiredPermissions = listOf(Manifest.permission.CAMERA),
                )
            )
            steps.add(
                TaskStep(
                    stepIndex = 2,
                    actionId = "launch_app",
                    description = "Open the camera app",
                    action = AndroidAction.LaunchApp("camera"),
                )
            )
            return steps to null
        }

        // 2. "Open this app and help me find its settings" / "Open <app> and help me find its settings"
        if ((lower.startsWith("open") || lower.contains("find")) && lower.contains("settings")) {
            val appMatch = Regex("open (?:the )?([a-zA-Z0-9_-]+) (?:app )?(?:and|to) (?:help me )?find (?:its )?settings").find(lower)
            val appName = appMatch?.groupValues?.get(1) ?: "app"
            steps.add(
                TaskStep(
                    stepIndex = 1,
                    actionId = "open_settings",
                    description = "Open system application settings for $appName",
                    action = AndroidAction.OpenSystemSettings(setting = "app_details", packageName = appName.takeIf { it != "app" }),
                )
            )
            steps.add(
                TaskStep(
                    stepIndex = 2,
                    actionId = "describe_screen",
                    description = "Analyze the settings screen and guide the user",
                    action = AndroidAction.DescribeScreen(prompt = "Help the user find settings in this view"),
                    requiredPermissions = listOf("android.permission.MEDIA_PROJECTION"),
                )
            )
            return steps to null
        }

        // 3. "Read the latest notification and draft a reply"
        if (lower.contains("notification") && (lower.contains("draft") || lower.contains("reply"))) {
            steps.add(
                TaskStep(
                    stepIndex = 1,
                    actionId = "read_latest_notification",
                    description = "Read the latest incoming notification",
                    action = AndroidAction.ReadLatestNotification(),
                )
            )
            steps.add(
                TaskStep(
                    stepIndex = 2,
                    actionId = "draft_notification_reply",
                    description = "Draft an appropriate context-aware reply",
                    action = AndroidAction.DraftNotificationReply(),
                    inputPipes = mapOf("notification_key" to "targetKey", "sender" to "targetSender"),
                )
            )
            return steps to null
        }

        // 4. "Find a contact, prepare a message, and ask me before sending it"
        if (lower.contains("contact") && (lower.contains("message") || lower.contains("sms") || lower.contains("text"))) {
            val nameMatch = Regex("(?:find|search|lookup) (?:contact )?([a-zA-Z]+)").find(clean)
            val contactQuery = nameMatch?.groupValues?.get(1) ?: ""

            if (contactQuery.isBlank()) {
                return emptyList<TaskStep>() to "Which contact would you like me to find?"
            }

            steps.add(
                TaskStep(
                    stepIndex = 1,
                    actionId = "lookup_contact",
                    description = "Look up contact '$contactQuery' in address book",
                    action = AndroidAction.LookUpContact(contactQuery),
                    requiredPermissions = listOf(Manifest.permission.READ_CONTACTS),
                )
            )
            steps.add(
                TaskStep(
                    stepIndex = 2,
                    actionId = "compose_sms",
                    description = "Prepare text message and request confirmation before sending",
                    action = AndroidAction.ComposeSms(
                        recipient = contactQuery,
                        message = "Hi! Let me know when you're available.",
                        confirmed = false,
                        directSend = false
                    ),
                    inputPipes = mapOf("name" to "recipient"),
                    isConsequential = true
                )
            )
            return steps to null
        }

        // 5. "Open the relevant settings page and guide me through the remaining steps"
        if (lower.contains("settings") && lower.contains("guide")) {
            steps.add(
                TaskStep(
                    stepIndex = 1,
                    actionId = "open_settings",
                    description = "Open general system settings",
                    action = AndroidAction.OpenSystemSettings(setting = "settings"),
                )
            )
            steps.add(
                TaskStep(
                    stepIndex = 2,
                    actionId = "describe_screen",
                    description = "Scan visible options and provide step-by-step guidance",
                    action = AndroidAction.DescribeScreen(prompt = "Guide the user through these settings steps"),
                    requiredPermissions = listOf("android.permission.MEDIA_PROJECTION"),
                )
            )
            return steps to null
        }

        // Single supported action fallback or ambiguous
        return emptyList<TaskStep>() to "I didn't recognize all the steps for '$request'. Could you clarify what you'd like me to do first?"
    }
}

/**
 * Coordinates multi-step assistant task execution with prerequisite checks,
 * ordered execution, result piping, cooperative cancellation, and accurate partial reporting.
 */
class TaskCoordinator(
    private val executor: ActionExecutor,
    private val scope: CoroutineScope? = null,
) {
    companion object {
        private const val TAG = "TaskCoordinator"
        const val MAX_STEPS = 5
        const val DEFAULT_STEP_TIMEOUT_MS = 10_000L
        const val TASK_TIMEOUT_MS = 30_000L

        private val tokenGenerator = AtomicLong(1L)
        private val activeTaskJobs = ConcurrentHashMap<String, Job>()
        private val activeTaskTokens = ConcurrentHashMap<String, Long>()
    }

    private val _activeTask = MutableStateFlow<MultiStepTaskState?>(null)
    val activeTask: StateFlow<MultiStepTaskState?> = _activeTask.asStateFlow()

    /**
     * Cancels an active running task cleanly and prevents any subsequent steps.
     * Accurately preserves whether previous steps completed or had irreversible side effects.
     */
    fun cancelTask(taskId: String, reason: String = "Cancelled by user"): Boolean {
        val job = activeTaskJobs.remove(taskId)
        val current = _activeTask.value

        if (current != null && current.taskId == taskId) {
            val updatedSteps = current.steps.map { step ->
                when (step.status) {
                    StepStatus.RUNNING -> step.copy(status = StepStatus.CANCELLED)
                    StepStatus.PENDING -> step.copy(status = StepStatus.SKIPPED)
                    else -> step
                }
            }

            val irreversibleNote = if (current.irreversibleActionsCompleted.isNotEmpty()) {
                "Note: ${current.irreversibleActionsCompleted.joinToString("; ")} was already dispatched and cannot be undone."
            } else null

            _activeTask.value = current.copy(
                steps = updatedSteps,
                overallStatus = if (current.completedStepsCount > 0) TaskOverallStatus.PARTIALLY_COMPLETED else TaskOverallStatus.CANCELLED,
                isCancelled = true,
                cancellationReason = reason,
                summary = "Task was cancelled. Completed ${current.completedStepsCount} of ${current.totalSteps} steps." +
                        (irreversibleNote?.let { " $it" } ?: "")
            )
        }

        if (job != null && job.isActive) {
            job.cancel(CancellationException(reason))
            return true
        }
        return false
    }

    fun cancelAll() {
        val current = _activeTask.value
        if (current != null) {
            cancelTask(current.taskId, "All tasks cancelled")
        }
        activeTaskJobs.values.forEach { it.cancel() }
        activeTaskJobs.clear()
        activeTaskTokens.clear()
    }

    /**
     * Executes a structured list of [steps] with input piping and cancellation support.
     */
    suspend fun executeTask(
        taskId: String,
        originalGoal: String,
        steps: List<TaskStep>,
    ): TaskExecutionReport = withContext(Dispatchers.Default) {
        if (taskId.isBlank()) {
            return@withContext TaskExecutionReport(
                taskId = "invalid",
                originalGoal = originalGoal,
                totalSteps = 0,
                completedSteps = 0,
                failedSteps = 0,
                skippedSteps = 0,
                cancelledSteps = 0,
                status = TaskOverallStatus.FAILED,
                summary = "Task ID cannot be blank.",
                stepDetails = emptyList()
            )
        }

        if (steps.isEmpty()) {
            return@withContext TaskExecutionReport(
                taskId = taskId,
                originalGoal = originalGoal,
                totalSteps = 0,
                completedSteps = 0,
                failedSteps = 0,
                skippedSteps = 0,
                cancelledSteps = 0,
                status = TaskOverallStatus.FAILED,
                summary = "Task contains no steps to execute.",
                stepDetails = emptyList()
            )
        }

        if (steps.size > MAX_STEPS) {
            return@withContext TaskExecutionReport(
                taskId = taskId,
                originalGoal = originalGoal,
                totalSteps = steps.size,
                completedSteps = 0,
                failedSteps = 0,
                skippedSteps = steps.size,
                cancelledSteps = 0,
                status = TaskOverallStatus.FAILED,
                summary = "Task exceeds maximum allowed limit of $MAX_STEPS steps.",
                stepDetails = steps
            )
        }

        val token = tokenGenerator.incrementAndGet()
        activeTaskTokens[taskId] = token

        val currentJob = coroutineContext[Job]
        if (currentJob != null) {
            activeTaskJobs[taskId] = currentJob
        }

        val mutableSteps = steps.map { it.copy() }.toMutableList()
        val accumulatedData = mutableMapOf<String, Any?>()
        val irreversibleCompleted = mutableListOf<String>()

        var taskState = MultiStepTaskState(
            taskId = taskId,
            originalGoal = originalGoal,
            steps = mutableSteps,
            currentStepIndex = 0,
            overallStatus = TaskOverallStatus.RUNNING,
            executionToken = token
        )
        _activeTask.value = taskState

        var completedCount = 0
        var failedCount = 0
        var skippedCount = 0
        var cancelledCount = 0
        var earlyStopStatus: TaskOverallStatus? = null
        var earlyStopSummary: String? = null
        var clarificationQuestion: String? = null

        val result = withTimeoutOrNull(TASK_TIMEOUT_MS) {
            for (i in 0 until mutableSteps.size) {
                // Verify cancellation or token staleness
                if (activeTaskTokens[taskId] != token || taskState.isCancelled || currentJob?.isCancelled == true) {
                    Log.i(TAG, "Task $taskId cancelled or superseded before step ${i + 1}")
                    earlyStopStatus = if (completedCount > 0) TaskOverallStatus.PARTIALLY_COMPLETED else TaskOverallStatus.CANCELLED
                    earlyStopSummary = "Task cancelled. Completed $completedCount of ${mutableSteps.size} steps."
                    for (j in i until mutableSteps.size) {
                        mutableSteps[j] = mutableSteps[j].copy(status = StepStatus.SKIPPED)
                        skippedCount++
                    }
                    break
                }

                val currentStep = mutableSteps[i]
                mutableSteps[i] = currentStep.copy(status = StepStatus.RUNNING)
                taskState = taskState.copy(currentStepIndex = i + 1, steps = mutableSteps.toList())
                _activeTask.value = taskState

                // 1. Check prerequisites & permissions before running
                val missingPerm = currentStep.requiredPermissions.firstOrNull { perm ->
                    !executor.registry.hasPermission(perm)
                }
                if (missingPerm != null) {
                    Log.w(TAG, "Step ${i + 1} (${currentStep.actionId}) missing permission: $missingPerm")
                    val permResult = ActionResult.permissionRequired(
                        missingPerm,
                        "Step ${i + 1} requires permission: $missingPerm."
                    )
                    mutableSteps[i] = currentStep.copy(status = StepStatus.FAILED, result = permResult)
                    failedCount++

                    for (j in (i + 1) until mutableSteps.size) {
                        mutableSteps[j] = mutableSteps[j].copy(status = StepStatus.SKIPPED)
                        skippedCount++
                    }
                    earlyStopStatus = TaskOverallStatus.FAILED
                    earlyStopSummary = "Stopped at step ${i + 1} (${currentStep.description}): Missing permission $missingPerm."
                    break
                }

                // 2. Input piping from previous step outputs
                var actionToRun = currentStep.action
                if (currentStep.inputPipes.isNotEmpty()) {
                    actionToRun = pipeInputs(actionToRun, currentStep.inputPipes, accumulatedData)
                }

                // 3. Consequential Action Gate
                if (actionToRun.requiresConfirmation && !isStepConfirmed(actionToRun)) {
                    Log.i(TAG, "Step ${i + 1} (${currentStep.actionId}) requires user confirmation.")
                    val confResult = ActionResult.needsConfirmation(
                        spoken = "Please confirm step ${i + 1}: ${currentStep.description}.",
                        actionId = currentStep.actionId,
                        payload = accumulatedData
                    )
                    mutableSteps[i] = currentStep.copy(status = StepStatus.PENDING, result = confResult)
                    earlyStopStatus = TaskOverallStatus.NEEDS_CONFIRMATION
                    earlyStopSummary = "Waiting for confirmation before executing: ${currentStep.description}."
                    for (j in (i + 1) until mutableSteps.size) {
                        mutableSteps[j] = mutableSteps[j].copy(status = StepStatus.SKIPPED)
                        skippedCount++
                    }
                    break
                }

                // 4. Execute atomic step with step timeout
                val stepOutcome = try {
                    withTimeoutOrNull(DEFAULT_STEP_TIMEOUT_MS) {
                        executor.execute(actionToRun)
                    } ?: ActionResult.failure("Step timed out.", error = "step_timeout")
                } catch (e: CancellationException) {
                    ActionResult.cancelled("Step cancelled: ${e.message}")
                } catch (e: Exception) {
                    ActionResult.failure("Step failed: ${e.message}", error = e.javaClass.simpleName)
                }

                mutableSteps[i] = currentStep.copy(result = stepOutcome)

                // 5. Evaluate outcome
                when (stepOutcome.status) {
                    ActionResultStatus.SUCCESS -> {
                        mutableSteps[i] = mutableSteps[i].copy(status = StepStatus.COMPLETED)
                        completedCount++
                        accumulatedData.putAll(stepOutcome.data)

                        if (currentStep.isConsequential) {
                            irreversibleCompleted.add(currentStep.description)
                        }
                    }
                    ActionResultStatus.NEEDS_CONFIRMATION -> {
                        mutableSteps[i] = mutableSteps[i].copy(status = StepStatus.PENDING)
                        earlyStopStatus = TaskOverallStatus.NEEDS_CONFIRMATION
                        earlyStopSummary = stepOutcome.spokenMessage
                        for (j in (i + 1) until mutableSteps.size) {
                            mutableSteps[j] = mutableSteps[j].copy(status = StepStatus.SKIPPED)
                            skippedCount++
                        }
                        break
                    }
                    ActionResultStatus.CANCELLED -> {
                        mutableSteps[i] = mutableSteps[i].copy(status = StepStatus.CANCELLED)
                        cancelledCount++
                        earlyStopStatus = if (completedCount > 0) TaskOverallStatus.PARTIALLY_COMPLETED else TaskOverallStatus.CANCELLED
                        earlyStopSummary = "Cancelled during step ${i + 1} (${currentStep.description})."
                        for (j in (i + 1) until mutableSteps.size) {
                            mutableSteps[j] = mutableSteps[j].copy(status = StepStatus.SKIPPED)
                            skippedCount++
                        }
                        break
                    }
                    ActionResultStatus.PERMISSION_REQUIRED -> {
                        mutableSteps[i] = mutableSteps[i].copy(status = StepStatus.FAILED)
                        failedCount++
                        earlyStopStatus = TaskOverallStatus.FAILED
                        earlyStopSummary = "Step ${i + 1} requires permission: ${stepOutcome.spokenMessage}"
                        for (j in (i + 1) until mutableSteps.size) {
                            mutableSteps[j] = mutableSteps[j].copy(status = StepStatus.SKIPPED)
                            skippedCount++
                        }
                        break
                    }
                    ActionResultStatus.UNSUPPORTED, ActionResultStatus.FAILURE -> {
                        mutableSteps[i] = mutableSteps[i].copy(status = StepStatus.FAILED)
                        failedCount++

                        // Check if ambiguity requires clarification
                        if (stepOutcome.error == "ambiguous_contact" || stepOutcome.error == "ambiguous_app") {
                            clarificationQuestion = stepOutcome.spokenMessage
                            earlyStopStatus = TaskOverallStatus.CLARIFICATION_REQUIRED
                            earlyStopSummary = stepOutcome.spokenMessage
                        } else {
                            earlyStopStatus = if (completedCount > 0) TaskOverallStatus.PARTIALLY_COMPLETED else TaskOverallStatus.FAILED
                            earlyStopSummary = "Stopped at step ${i + 1} (${currentStep.description}): ${stepOutcome.spokenMessage}"
                        }

                        for (j in (i + 1) until mutableSteps.size) {
                            mutableSteps[j] = mutableSteps[j].copy(status = StepStatus.SKIPPED)
                            skippedCount++
                        }
                        break
                    }
                }

                taskState = taskState.copy(
                    steps = mutableSteps.toList(),
                    irreversibleActionsCompleted = irreversibleCompleted.toList()
                )
                _activeTask.value = taskState
            }

            true
        }

        activeTaskJobs.remove(taskId)

        val finalStatus = earlyStopStatus ?: if (completedCount == mutableSteps.size) {
            TaskOverallStatus.COMPLETED
        } else if (completedCount > 0) {
            TaskOverallStatus.PARTIALLY_COMPLETED
        } else {
            TaskOverallStatus.FAILED
        }

        val irreversibleNote = if (irreversibleCompleted.isNotEmpty()) {
            "Irreversible action already taken: ${irreversibleCompleted.joinToString("; ")}. This action cannot be recalled."
        } else null

        val finalSummary = earlyStopSummary ?: when (finalStatus) {
            TaskOverallStatus.COMPLETED -> "Successfully completed all $completedCount steps."
            TaskOverallStatus.PARTIALLY_COMPLETED -> "Partially completed $completedCount of ${mutableSteps.size} steps."
            TaskOverallStatus.CANCELLED -> "Task was cancelled."
            TaskOverallStatus.NEEDS_CONFIRMATION -> "Task is paused awaiting your confirmation."
            TaskOverallStatus.CLARIFICATION_REQUIRED -> clarificationQuestion ?: "Clarification needed."
            else -> "Task failed to complete all steps."
        }

        val report = TaskExecutionReport(
            taskId = taskId,
            originalGoal = originalGoal,
            totalSteps = mutableSteps.size,
            completedSteps = completedCount,
            failedSteps = failedCount,
            skippedSteps = skippedCount,
            cancelledSteps = cancelledCount,
            status = finalStatus,
            summary = finalSummary,
            stepDetails = mutableSteps,
            clarificationQuestion = clarificationQuestion,
            irreversibleNote = irreversibleNote,
            data = accumulatedData
        )

        _activeTask.value = taskState.copy(
            overallStatus = finalStatus,
            summary = finalSummary,
            irreversibleActionsCompleted = irreversibleCompleted
        )

        return@withContext report
    }

    private fun isStepConfirmed(action: AndroidAction): Boolean {
        return when (action) {
            is AndroidAction.InitiateCall -> action.confirmed
            is AndroidAction.ComposeSms -> action.confirmed
            is AndroidAction.ReplyToNotification -> action.confirmed
            is AndroidAction.TapScreen -> action.confirmed
            else -> true
        }
    }

    private fun pipeInputs(
        action: AndroidAction,
        pipes: Map<String, String>,
        accumulated: Map<String, Any?>
    ): AndroidAction {
        return when (action) {
            is AndroidAction.ComposeSms -> {
                val targetName = accumulated["name"] as? String ?: action.recipient
                action.copy(recipient = targetName)
            }
            is AndroidAction.DraftNotificationReply -> {
                val key = accumulated["key"] as? String ?: action.targetKey
                val sender = accumulated["sender"] as? String ?: action.targetSender
                action.copy(targetKey = key, targetSender = sender)
            }
            is AndroidAction.InitiateCall -> {
                val targetName = accumulated["name"] as? String ?: action.queryOrNumber
                action.copy(queryOrNumber = targetName)
            }
            else -> action
        }
    }
}
