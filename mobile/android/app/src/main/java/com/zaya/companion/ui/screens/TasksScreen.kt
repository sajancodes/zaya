package com.zaya.companion.ui.screens

import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.ui.EmptyNote
import com.zaya.companion.ui.KeyValue
import com.zaya.companion.ui.SectionCard
import com.zaya.companion.ui.StatusChip
import com.zaya.companion.ui.humanAgo
import com.zaya.companion.ui.theme.ZayaAccent
import kotlinx.coroutines.launch

/**
 * The laptop's task runtime, read-only.
 *
 * Tasks are created by talking to Zaya (here or anywhere else); this screen shows
 * what she is doing with them. Nothing on the phone can start or edit a task —
 * that stays a conversation, which is the whole point of Zaya being one runtime.
 */
@Composable
fun TasksScreen(runtime: ZayaRuntime, onBack: () -> Unit) {
    val tasks by runtime.model.tasks.collectAsStateWithLifecycle()
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
                    subtitle = "${tasks.count { it.isActive }} active of ${tasks.size}",
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
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (tasks.isEmpty()) {
                item { EmptyNote("No tasks yet. Ask Zaya for something in Chat.") }
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
