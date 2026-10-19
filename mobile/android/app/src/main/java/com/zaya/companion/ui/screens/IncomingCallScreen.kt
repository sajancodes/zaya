package com.zaya.companion.ui.screens

import androidx.compose.runtime.*
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.protocol.CallUiState
import com.zaya.companion.runtime.ZayaRuntime
import kotlinx.coroutines.delay

/** Answering keeps this activity open; only the end of a call dismisses it. */
@Composable
fun IncomingCallScreen(runtime: ZayaRuntime, onDismiss: () -> Unit) {
    val call by runtime.model.call.collectAsStateWithLifecycle()
    LaunchedEffect(call) {
        if (call is CallUiState.Idle) { delay(1200); onDismiss() }
    }
    CallScreen(runtime, onMinimize = onDismiss)
}
