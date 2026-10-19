package com.zaya.companion.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.protocol.CallUiState
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.ui.StatusChip
import com.zaya.companion.ui.ZayaFace
import com.zaya.companion.ui.theme.ZayaAccent

/**
 * Zaya calling, full screen. P0/P1 are the only priorities that reach this
 * screen; everything else arrives as a notification, exactly as the laptop
 * decided.
 */
@Composable
fun IncomingCallScreen(runtime: ZayaRuntime, onDismiss: () -> Unit) {
    val call by runtime.model.call.collectAsStateWithLifecycle()
    val visual by runtime.model.visual.collectAsStateWithLifecycle()
    val ringing = call as? CallUiState.Ringing

    LaunchedEffect(ringing?.call?.callId) {
        if (ringing == null) onDismiss()
    }

    val info = ringing?.call ?: return
    Column(
        Modifier
            .fillMaxSize()
            .padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        StatusChip(
            text = info.priorityName.ifBlank { "important" },
            color = if (info.priority <= Protocol.P1_IMMEDIATE) ZayaAccent.red else ZayaAccent.amber,
        )
        Spacer(Modifier.height(12.dp))
        Text(
            text = info.title.ifBlank { "Zaya is calling" },
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
            textAlign = TextAlign.Center,
        )
        if (info.detail.isNotBlank()) {
            Text(
                text = info.detail,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 6.dp),
            )
        }
        if (info.reason.isNotBlank() && info.reason != info.detail) {
            Text(
                text = info.reason,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 4.dp),
            )
        }

        ZayaFace(
            state = Protocol.SPEAKING,
            emotion = visual.emotion,
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
        )

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Button(
                onClick = { runtime.answer(info.callId) },
                modifier = Modifier.weight(1f),
            ) { Text("Answer") }
            OutlinedButton(
                onClick = { runtime.decline(info.callId) },
                colors = ButtonDefaults.outlinedButtonColors(contentColor = ZayaAccent.red),
                modifier = Modifier.weight(1f),
            ) { Text("Decline") }
        }
        Spacer(Modifier.height(8.dp))
    }
}
