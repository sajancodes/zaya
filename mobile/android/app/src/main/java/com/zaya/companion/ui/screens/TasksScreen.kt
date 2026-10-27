package com.zaya.companion.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.action.MultiStepTaskState
import com.zaya.companion.action.StepStatus
import com.zaya.companion.action.TaskOverallStatus
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.ui.EmptyNote
import com.zaya.companion.ui.KeyValue
import com.zaya.companion.ui.SectionCard
import com.zaya.companion.ui.StatusChip
import com.zaya.companion.ui.humanAgo
import com.zaya.companion.ui.theme.ZayaAccent
import kotlinx.coroutines.launch

/**
 * Displays both on-device multi-step task execution progress with live cancellation,
 * and the laptop's runtime task list.
 */
@Composable
fun TasksScreen(runtime: ZayaRuntime, onBack: () -> Unit) {
    val tasks by runtime.model.tasks.collectAsStateWithLifecycle()
    val localTask by runtime.taskCoordinator.activeTask.collectAsStateWithLifecycle()
    val status by runtime.connection.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var refreshing by remember { mutableStateOf(false) }

    LaunchedEffect(status.isOnline) {
        if (status.isOnline) runtime.refreshTasks()
    }

    Column(Modifier.fillMaxSize()) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(start = 16.dp, end = 16.dp, top = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                ScreenHeader(
                    title = "Tasks",
                    subtitle = if (localTask?.isRunning == true) "Active multi-step task running"
                    else "${tasks.count { it.isActive }} active on laptop",
                    onBack = onBack,
                )
            }
            OutlinedButton(
                onClick = {
                    refreshing = true
                    scope.launch {
                        runtime.refreshTasks()
                        refreshing = false
                    }
                },
                enabled = !refreshing,
            ) { Text(if (refreshing) "…" else "Refresh") }
        }

        LazyColumn(
            Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // Local Multi-Step Task Progress Card
            localTask?.let { active ->
                item(key = "local_active_task") {
                    ActiveTaskCard(
                        task = active,
                        onCancel = {
                            runtime.taskCoordinator.cancelTask(active.taskId, "Cancelled by user")
                        }
                    )
                }
            }

            if (tasks.isEmpty() && localTask == null) {
                item { EmptyNote("No tasks yet. Ask Zaya for something in Chat.") }
            }

            item {
                Text(
                    text = "Runtime Tasks",
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp, bottom = 2.dp)
                )
            }

            items(tasks, key = { it.taskId }) { task ->
                SectionCard(
                    title = task.goal.ifBlank { task.taskId },
                    subtitle = task.source.ifBlank { "runtime" },
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        StatusChip(
                            text = task.state,
                            color = when (task.state.lowercase()) {
                                "completed" -> ZayaAccent.green
                                "failed" -> ZayaAccent.red
                                "cancelled" -> ZayaAccent.muted
                                else -> ZayaAccent.amber
                            },
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = humanAgo((task.updatedAt * 1000).toLong()),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Spacer(Modifier.height(8.dp))
                    if (task.activeStep != null) KeyValue("Now", task.activeStep)
                    if (task.attempts > 1) KeyValue("Attempts", task.attempts.toString())
                    KeyValue("Evidence", task.evidenceCount.toString())
                    KeyValue("Side effects", task.sideEffectCount.toString())
                    if (task.error != null) {
                        Spacer(Modifier.height(6.dp))
                        Text(
                            text = task.error,
                            style = MaterialTheme.typography.bodySmall,
                            color = ZayaAccent.red,
                        )
                    }
                }
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}

@Composable
fun ActiveTaskCard(
    task: MultiStepTaskState,
    onCancel: () -> Unit,
) {
    SectionCard(
        title = task.originalGoal.ifBlank { "Multi-Step Assistant Task" },
        subtitle = "Task ID: ${task.taskId.take(16)}",
    ) {
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                StatusChip(
                    text = task.overallStatus.name.replace('_', ' '),
                    color = when (task.overallStatus) {
                        TaskOverallStatus.COMPLETED -> ZayaAccent.green
                        TaskOverallStatus.PARTIALLY_COMPLETED -> ZayaAccent.amber
                        TaskOverallStatus.FAILED -> ZayaAccent.red
                        TaskOverallStatus.CANCELLED -> ZayaAccent.muted
                        TaskOverallStatus.RUNNING -> ZayaAccent.blue
                        TaskOverallStatus.NEEDS_CONFIRMATION -> ZayaAccent.amber
                        TaskOverallStatus.CLARIFICATION_REQUIRED -> ZayaAccent.amber
                        TaskOverallStatus.NOT_STARTED -> ZayaAccent.quiet
                    }
                )
                Spacer(Modifier.width(8.dp))
                if (task.isRunning) {
                    Text(
                        text = "Step ${task.currentStepIndex} of ${task.totalSteps}",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }

            if (task.isRunning) {
                OutlinedButton(
                    onClick = onCancel,
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = ZayaAccent.red),
                ) {
                    Text("Cancel Task")
                }
            }
        }

        Spacer(Modifier.height(10.dp))

        // Step by step breakdown
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(8.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f))
                .padding(10.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            task.steps.forEach { step ->
                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = "${step.stepIndex}. ",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = step.description,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                    }
                    StatusChip(
                        text = step.status.name,
                        color = when (step.status) {
                            StepStatus.COMPLETED -> ZayaAccent.green
                            StepStatus.RUNNING -> ZayaAccent.blue
                            StepStatus.FAILED -> ZayaAccent.red
                            StepStatus.CANCELLED -> ZayaAccent.muted
                            StepStatus.SKIPPED -> ZayaAccent.quiet
                            StepStatus.PENDING -> ZayaAccent.amber
                        }
                    )
                }
                if (step.result != null && step.status in setOf(StepStatus.FAILED, StepStatus.CANCELLED)) {
                    Text(
                        text = "Outcome: ${step.result?.spokenMessage}",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (step.status == StepStatus.FAILED) ZayaAccent.red else ZayaAccent.muted,
                        modifier = Modifier.padding(start = 16.dp)
                    )
                }
            }
        }

        if (task.summary.isNotBlank()) {
            Spacer(Modifier.height(8.dp))
            Text(
                text = task.summary,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        if (task.irreversibleActionsCompleted.isNotEmpty()) {
            Spacer(Modifier.height(6.dp))
            Text(
                text = "Irreversible: ${task.irreversibleActionsCompleted.joinToString(", ")} (cannot be undone)",
                style = MaterialTheme.typography.labelSmall,
                color = ZayaAccent.amber
            )
        }
    }
}
