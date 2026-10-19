package com.zaya.companion.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.protocol.CallUiState
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.ui.SectionCard
import com.zaya.companion.core.ZayaBuild
import kotlinx.coroutines.launch

@Composable
fun UpdateCard(runtime: ZayaRuntime, showWhenCurrent: Boolean = true) {
    val state by runtime.updates.state.collectAsStateWithLifecycle()
    val call by runtime.model.call.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) { runtime.updates.check() }
    if (!showWhenCurrent && state.available == null) return
    val busy = state.checking || state.downloading
    SectionCard(title = if (state.available != null) "Update available" else "App updates",
        subtitle = "Installed version ${ZayaBuild.VERSION}") {
        if (state.message.isNotBlank()) Text(state.message)
        if (state.downloading) {
            Spacer(Modifier.height(8.dp))
            LinearProgressIndicator(progress = { state.percent / 100f }, modifier = Modifier.fillMaxWidth())
            Text("${state.percent}% downloaded")
        }
        if (call !is CallUiState.Idle) Text("Finish your call before installing an update.")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(enabled = !busy, onClick = { scope.launch { runtime.updates.check(force = true) } }) {
                Text(if (state.checking) "Checking…" else "Check for updates")
            }
            if (state.available != null) Button(enabled = !busy && call is CallUiState.Idle,
                onClick = {
                    scope.launch {
                        if (state.ready == null) runtime.updates.download()
                        if (runtime.model.call.value is CallUiState.Idle) runtime.updates.install(context)
                    }
                }) { Text(if (state.ready != null) "Install update" else "Update now") }
        }
    }
}
