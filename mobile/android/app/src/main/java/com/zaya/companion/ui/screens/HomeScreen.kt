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
    val serverName by runtime.model.serverName.collectAsStateWithLifecycle()
    val voice by runtime.model.voice.collectAsStateWithLifecycle()
    val call by runtime.model.call.collectAsStateWithLifecycle()
    val notifications by runtime.model.notifications.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    val context = androidx.compose.ui.platform.LocalContext.current

    Column(Modifier.fillMaxSize()) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(start = 20.dp, end = 12.dp, top = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    text = serverName,
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = visual.state.lowercase().replace('_', ' ') +
                        if (visual.emotion != "neutral") " · ${visual.emotion}" else "",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            ConnectionPill(status)
            IconButton(onClick = onOpenNotifications) {
                Icon(Icons.Filled.Notifications, contentDescription = "Notifications")
            }
        }

        ZayaFace(
            state = visual.state,
            emotion = visual.emotion,
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .padding(horizontal = 8.dp),
        )

        Column(Modifier.padding(horizontal = 16.dp)) {
            if (caption.text.isNotBlank()) {
                SectionCard {
                    Text(
                        text = caption.text,
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                }
                Spacer(Modifier.height(10.dp))
            }
            if (voice.note.isNotBlank()) {
                Note(voice.note, ZayaAccent.amber)
                Spacer(Modifier.height(10.dp))
            }

            CommandInput(runtime, placeholder = "Type to Zaya…")
            Spacer(Modifier.height(10.dp))

            Row(verticalAlignment = Alignment.CenterVertically) {
                val ringing = call
                when (ringing) {
                    is CallUiState.Ringing -> Button(
                        onClick = { runtime.answer(ringing.call.callId) },
                        modifier = Modifier.weight(1f),
                    ) {
                        Icon(Icons.Filled.Call, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Answer Zaya")
                    }

                    is CallUiState.Active -> OutlinedButton(
                        onClick = { runtime.endCall() },
                        modifier = Modifier.weight(1f),
                    ) { Text("End the call") }

                    CallUiState.Idle -> OutlinedButton(
                        onClick = { runtime.startCall() },
                        modifier = Modifier.weight(1f),
                    ) {
                        Icon(Icons.Filled.Call, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Call Zaya")
                    }
                }
                Spacer(Modifier.width(10.dp))
                OutlinedButton(onClick = onOpenSettings) { Text("Settings") }
            }

            Spacer(Modifier.height(6.dp))
            ConnectionDetail(status)
            Spacer(Modifier.height(14.dp))
        }
    }
}

/** The shared "say something to Zaya" box, used by Home and Chat. */
@Composable
fun CommandInput(runtime: ZayaRuntime, placeholder: String = "Message Zaya…") {
    var text by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val status by runtime.connection.collectAsStateWithLifecycle()

    fun submit() {
        val message = text.trim()
        if (message.isEmpty()) return
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
            enabled = text.isNotBlank(),
        ) {
            Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
        }
    }
    if (!status.isOnline) {
        Text(
            text = if (status.phase == com.zaya.companion.protocol.ConnectionPhase.UNPAIRED) {
                "Pair with your laptop first — the message will go as soon as you do."
            } else {
                "Offline: this is kept and sent the moment Zaya is reachable."
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
