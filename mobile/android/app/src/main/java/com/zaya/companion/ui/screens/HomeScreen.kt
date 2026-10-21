package com.zaya.companion.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.TextButton
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.ui.ConnectionDetail
import com.zaya.companion.ui.ConnectionPill
import com.zaya.companion.ui.EmptyNote
import com.zaya.companion.ui.Note
import com.zaya.companion.ui.SectionCard
import com.zaya.companion.ui.ZayaFace
import com.zaya.companion.ui.humanAgo
import com.zaya.companion.ui.theme.ZayaAccent
import com.zaya.companion.protocol.CallUiState
import com.zaya.companion.protocol.Protocol
import kotlinx.coroutines.launch

/**
 * The first thing the owner sees: Zaya, not a menu.
 *
 * Her face takes the screen, her state comes from the laptop, and the only
 * controls are the ones a person actually reaches for — talk, type, call.
 */
@Composable
fun HomeScreen(
    runtime: ZayaRuntime,
    onOpenNotifications: () -> Unit,
    onOpenSettings: () -> Unit,
) {
    val visual by runtime.model.visual.collectAsStateWithLifecycle()
    val caption by runtime.model.caption.collectAsStateWithLifecycle()
    val status by runtime.connection.collectAsStateWithLifecycle()
    val voice by runtime.model.voice.collectAsStateWithLifecycle()
    val call by runtime.model.call.collectAsStateWithLifecycle()
    val notifications by runtime.model.notifications.collectAsStateWithLifecycle()

    BoxWithConstraints(Modifier.fillMaxSize().imePadding()) {
        val faceHeight = (maxHeight * 0.38f).coerceIn(160.dp, 280.dp)
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Zaya", style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.SemiBold)
                    Text("A little closer, wherever you are.", style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                BadgedBox(badge = { if (notifications.any { !it.read }) Badge() }) {
                    IconButton(onClick = onOpenNotifications) {
                        Icon(Icons.Filled.Notifications, contentDescription = "Notifications")
                    }
                }
            }

            Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(32.dp)).background(
                Brush.verticalGradient(listOf(MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.6f),
                    MaterialTheme.colorScheme.surface))), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.fillMaxWidth().padding(vertical = 16.dp)) {
                    ConnectionPill(status)
                    ZayaFace(state = visual.state, emotion = visual.emotion,
                        modifier = Modifier.fillMaxWidth().height(faceHeight))
                    Text(visual.state.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() },
                        style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                }
            }

            if (caption.text.isNotBlank()) SectionCard {
                Text(caption.text, style = MaterialTheme.typography.bodyLarge,
                    maxLines = 3, overflow = TextOverflow.Ellipsis)
            }
            if (voice.note.isNotBlank()) Note(voice.note, ZayaAccent.amber)

            Button(onClick = {
                when (val current = call) {
                    is CallUiState.Ringing -> runtime.answer(current.call.callId)
                    is CallUiState.Active, is CallUiState.Dialing -> runtime.endCall()
                    CallUiState.Idle -> runtime.startCall()
                }
            }, enabled = status.isOnline || call !is CallUiState.Idle,
                modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp),
                shape = RoundedCornerShape(20.dp)) {
                Icon(Icons.Filled.Call, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(when (call) {
                    is CallUiState.Ringing -> "Answer Zaya"
                    is CallUiState.Active, is CallUiState.Dialing -> "End call"
                    CallUiState.Idle -> "Call Zaya"
                })
            }
            SectionCard {
                Text("What's on your mind?", style = MaterialTheme.typography.titleSmall)
                Spacer(Modifier.height(8.dp))
                CommandInput(runtime, placeholder = "Message Zaya…")
            }
            if (!status.isOnline) TextButton(onClick = onOpenSettings, modifier = Modifier.fillMaxWidth()) {
                Text("Connect your laptop in Settings")
            }
            UpdateCard(runtime, showWhenCurrent = false)
        }
    }
}

/** The shared "say something to Zaya" box, used by Home and Chat. */
@Composable
fun CommandInput(runtime: ZayaRuntime, placeholder: String = "Message Zaya…") {
    var text by rememberSaveable { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val status by runtime.connection.collectAsStateWithLifecycle()

    fun submit() {
        val message = text.trim()
        if (message.isEmpty() || !status.isOnline) return
        text = ""
        scope.launch { runtime.send(message) }
    }

    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = text,
            onValueChange = { text = it.take(Protocol.MAX_TEXT) },
            placeholder = { Text(placeholder) },
            maxLines = 4,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
            keyboardActions = KeyboardActions(onSend = { submit() }),
            modifier = Modifier.weight(1f),
        )
        Spacer(Modifier.width(8.dp))
        IconButton(
            onClick = { submit() },
            enabled = text.isNotBlank() && status.isOnline,
        ) {
            Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
        }
    }
    if (!status.isOnline) {
        Text(
            text = if (status.phase == com.zaya.companion.protocol.ConnectionPhase.UNPAIRED) {
                "Pair with your laptop in Settings to send messages."
            } else {
                "Offline. Your draft stays here; send it once connected."
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

/** Everything the laptop wanted the owner to see, newest first. */
@Composable
fun NotificationsScreen(runtime: ZayaRuntime, onBack: () -> Unit) {
    val items by runtime.model.notifications.collectAsStateWithLifecycle()
    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        ScreenHeader("Notifications", "Sent by Zaya on your laptop", onBack)
        if (items.isEmpty()) {
            EmptyNote("Nothing yet.")
        }
        for (item in items) {
            SectionCard(
                title = item.title,
                subtitle = buildString {
                    append(item.priorityName.ifBlank { "priority ${item.priority}" })
                    append(" · ")
                    append(humanAgo(item.at))
                    if (item.source.isNotBlank()) append(" · ${item.source}")
                },
                modifier = Modifier.padding(bottom = 10.dp),
            ) {
                if (item.body.isNotBlank()) Text(item.body)
            }
        }
        Spacer(Modifier.height(24.dp))
    }
    androidx.compose.runtime.LaunchedEffect(Unit) { runtime.model.markNotificationsRead() }
}

@Composable
fun ScreenHeader(title: String, subtitle: String = "", onBack: (() -> Unit)? = null) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(bottom = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Start,
    ) {
        if (onBack != null) {
            OutlinedButton(onClick = onBack) { Text("Back") }
            Spacer(Modifier.width(12.dp))
        }
        Column {
            Text(
                text = title,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )
            if (subtitle.isNotBlank()) {
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
