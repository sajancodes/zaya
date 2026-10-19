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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.protocol.CallInfo
import com.zaya.companion.protocol.CallUiState
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.runtime.ZayaModel
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.ui.Note
import com.zaya.companion.ui.OutlinedToggle
import com.zaya.companion.ui.ZayaFace
import com.zaya.companion.ui.theme.ZayaAccent
import kotlinx.coroutines.delay

/**
 * The call screen: the same face, the same voice, plus the controls a phone call
 * needs. The laptop owns the call — answering, declining and ending here are
 * requests to it, mirrored back through `call.answered` / `call.ended`.
 */
@Composable
fun CallScreen(runtime: ZayaRuntime, onMinimize: () -> Unit) {
    val call by runtime.model.call.collectAsStateWithLifecycle()
    val visual by runtime.model.visual.collectAsStateWithLifecycle()
    val voice by runtime.model.voice.collectAsStateWithLifecycle()
    val output by runtime.model.outputTarget.collectAsStateWithLifecycle()
    var elapsed by remember { mutableLongStateOf(0L) }

    LaunchedEffect(call) {
        val active = call as? CallUiState.Active
        if (active == null) {
            elapsed = 0L
            return@LaunchedEffect
        }
        while (true) {
            elapsed = (System.currentTimeMillis() - active.answeredAt) / 1000
            delay(1_000)
        }
    }

    val ringing = call as? CallUiState.Ringing
    val active = call as? CallUiState.Active
    val info: CallInfo? = ringing?.call ?: active?.call

    Column(
        Modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = info?.title?.ifBlank { "Zaya" } ?: "Zaya",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            text = when {
                active != null -> ZayaModel.formatDuration(elapsed)
                ringing != null -> "Ringing…"
                else -> "No call in progress"
            },
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (info != null && info.reason.isNotBlank()) {
            Text(
                text = info.reason,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(top = 6.dp),
            )
        }

        ZayaFace(
            state = if (voice.micActive) Protocol.LISTENING else visual.state,
            emotion = visual.emotion,
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
        )

        VoiceMeter(runtime)

        if (voice.note.isNotBlank()) {
            Spacer(Modifier.height(8.dp))
            Note(voice.note, ZayaAccent.amber)
        }
        Spacer(Modifier.height(10.dp))

        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            OutlinedToggle(
                label = if (voice.muted) "Unmute" else "Mute",
                active = voice.muted,
                onClick = { runtime.setMuted(!voice.muted) },
                modifier = Modifier.weight(1f),
            )
            OutlinedButton(
                onClick = {
                    val next = when (output) {
                        Protocol.Output.DESKTOP -> Protocol.Output.PHONE
                        Protocol.Output.PHONE -> Protocol.Output.BOTH
                        else -> Protocol.Output.DESKTOP
                    }
                    runtime.changeOutputInBackground(next)
                },
                modifier = Modifier.weight(1f),
            ) {
                Text(
                    when (output) {
                        Protocol.Output.DESKTOP -> "Laptop"
                        Protocol.Output.PHONE -> "Phone"
                        Protocol.Output.BOTH -> "Both"
                        else -> "Voice"
                    },
                )
            }
        }

        Spacer(Modifier.height(10.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            when {
                ringing != null -> {
                    Button(
                        onClick = { runtime.answer(ringing.call.callId) },
                        modifier = Modifier.weight(1f),
                    ) { Text("Answer") }
                    Button(
                        onClick = { runtime.decline(ringing.call.callId) },
                        colors = ButtonDefaults.buttonColors(containerColor = ZayaAccent.red),
                        modifier = Modifier.weight(1f),
                    ) { Text("Decline") }
                }

                active != null -> {
                    Button(
                        onClick = { runtime.endCall() },
                        colors = ButtonDefaults.buttonColors(containerColor = ZayaAccent.red),
                        modifier = Modifier.weight(1f),
                    ) { Text("End call") }
                    OutlinedButton(onClick = onMinimize, modifier = Modifier.weight(1f)) {
                        Text("Hide")
                    }
                }

                else -> {
                    Button(onClick = { runtime.startCall() }, modifier = Modifier.weight(1f)) {
                        Text("Call Zaya")
                    }
                    OutlinedButton(onClick = onMinimize, modifier = Modifier.weight(1f)) {
                        Text("Back")
                    }
                }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

/**
 * A real level meter, not a decoration: it reads what the speaker is actually
 * playing, which is how the owner can tell "connected" from "heard".
 */
@Composable
private fun VoiceMeter(runtime: ZayaRuntime) {
    val voice by runtime.model.voice.collectAsStateWithLifecycle()
    var level by remember { mutableFloatStateOf(0f) }

    LaunchedEffect(voice.speakerActive) {
        while (true) {
            level = if (voice.speakerActive) runtime.outputLevel() else 0f
            delay(120)
        }
    }

    Row(
        Modifier
            .fillMaxWidth()
            .height(6.dp)
            .clip(RoundedCornerShape(50))
            .background(ZayaAccent.quiet),
    ) {
        Box(
            Modifier
                .fillMaxWidth((0.04f + level).coerceIn(0.04f, 1f))
                .fillMaxSize()
                .background(
                    if (voice.speakerActive) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        ZayaAccent.muted.copy(alpha = 0.4f)
                    },
                ),
        )
    }
}
