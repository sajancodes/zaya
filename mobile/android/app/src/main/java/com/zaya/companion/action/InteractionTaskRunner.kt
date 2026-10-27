package com.zaya.companion.action

import android.util.Log
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.util.concurrent.ConcurrentHashMap

data class TaskStepReport(
    val stepIndex: Int,
    val actionId: String,
    val status: ActionResultStatus,
    val message: String
)

data class BoundedTaskOutcome(
    val taskId: String,
    val success: Boolean,
    val message: String,
    val steps: List<TaskStepReport>
)

/**
 * Executes a strictly bounded sequence of assistant actions with timeouts, step verification,
 * and user cancellation support. Prevents runaway autonomous execution.
 */
class InteractionTaskRunner(private val executor: ActionExecutor) {

    companion object {
        private const val TAG = "InteractionTaskRunner"
        const val MAX_STEPS = 5
        const val TASK_TIMEOUT_MS = 15000L

        private val activeTasks = ConcurrentHashMap<String, Job>()

        fun cancelTask(taskId: String): Boolean {
            val job = activeTasks.remove(taskId)
            return if (job != null && job.isActive) {
                job.cancel(CancellationException("Task $taskId explicitly cancelled by user."))
                true
            } else {
                false
            }
        }

        fun cancelAllTasks() {
            activeTasks.values.forEach { it.cancel() }
            activeTasks.clear()
        }
    }

    suspend fun executeTask(
        taskId: String,
        actions: List<AndroidAction>
    ): ActionResult = withContext(Dispatchers.Default) {
        if (taskId.isBlank()) {
            return@withContext ActionResult.failure("Task ID cannot be blank.", error = "invalid_task_id")
        }

        if (actions.isEmpty()) {
            return@withContext ActionResult.failure("Task contains no actions to execute.", error = "empty_task")
        }

        if (actions.size > MAX_STEPS) {
            return@withContext ActionResult.failure(
                spoken = "Task exceeds maximum allowed limit of $MAX_STEPS actions.",
                error = "step_limit_exceeded"
            )
        }

        val stepReports = mutableListOf<TaskStepReport>()
        val parentJob = coroutineContext[Job]
        if (parentJob != null) {
            activeTasks[taskId] = parentJob
        }

        val result = withTimeoutOrNull(TASK_TIMEOUT_MS) {
            for ((index, action) in actions.withIndex()) {
                Log.d(TAG, "Executing task $taskId step ${index + 1}/${actions.size}: ${action.actionId}")

                val outcome = executor.execute(action)
                stepReports.add(
                    TaskStepReport(
                        stepIndex = index + 1,
                        actionId = action.actionId,
                        status = outcome.status,
                        message = outcome.spokenMessage
                    )
                )

                // If any step fails or needs confirmation/permission, halt sequence immediately
                if (outcome.status != ActionResultStatus.SUCCESS) {
                    Log.w(TAG, "Task $taskId stopped at step ${index + 1} with status ${outcome.status}")
                    return@withTimeoutOrNull outcome
                }
            }
            ActionResult.success(
                spoken = "Completed all ${actions.size} actions for task $taskId.",
                data = mapOf(
                    "task_id" to taskId,
                    "total_steps" to actions.size,
                    "completed" to true
                )
            )
        }

        activeTasks.remove(taskId)

        return@withContext result ?: ActionResult.failure(
            spoken = "Task $taskId timed out after ${TASK_TIMEOUT_MS / 1000} seconds.",
            error = "task_timeout"
        )
    }
}
