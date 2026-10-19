package com.zaya.companion.ui.screens

import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.protocol.WhatsappRow
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.ui.EmptyNote
import com.zaya.companion.ui.Note
import com.zaya.companion.ui.OutlinedToggle
import com.zaya.companion.ui.SectionCard
import com.zaya.companion.ui.StatusChip
import com.zaya.companion.ui.UntrustedQuote
import com.zaya.companion.ui.theme.ZayaAccent
import kotlinx.coroutines.launch

/**
 * WhatsApp, as the laptop sees it: read-only views plus the mode switches that
 * are the owner's to make. Every message body is quoted, never obeyed — the same
 * rule the runtime follows for contact text.
 */
@Composable
fun WhatsappScreen(runtime: ZayaRuntime, onBack: () -> Unit) {
    val feed by runtime.model.whatsapp.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var query by remember { mutableStateOf("") }
    var selected by remember { mutableStateOf<WhatsappRow?>(null) }

    LaunchedEffect(Unit) {
        runtime.whatsapp("status")
    }

    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
            ScreenHeader(
                title = "WhatsApp",
                subtitle = buildString {
                    append(feed.globalMode.ifBlank { "mode unknown" })
                    if (feed.aiActive) append(" · Zaya replying")
                    if (!feed.feedReady) append(" · feed not ready")
                },
                onBack = onBack,
            )
            Row(
                Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedToggle(
                    label = "Auto",
                    active = feed.globalMode == Protocol.WhatsappMode.GLOBAL_AUTO,
                    onClick = { scope.launch { runtime.setWhatsappMode("", Protocol.WhatsappMode.GLOBAL_AUTO) } },
                )
                OutlinedToggle(
                    label = "Observe only",
                    active = feed.globalMode == Protocol.WhatsappMode.GLOBAL_OBSERVE,
                    onClick = { scope.launch { runtime.setWhatsappMode("", Protocol.WhatsappMode.GLOBAL_OBSERVE) } },
                )
                for (action in listOf("recent", "unread", "important")) {
                    OutlinedButton(onClick = { scope.launch { runtime.whatsapp(action) } }) {
                        Text(action.replaceFirstChar { it.uppercase() })
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    placeholder = { Text("Search messages") },
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                OutlinedButton(
                    onClick = { scope.launch { runtime.whatsapp("search", query = query) } },
                    enabled = query.isNotBlank(),
                ) { Text("Search") }
            }
            if (feed.error.isNotBlank()) {
                Spacer(Modifier.height(8.dp))
                Note(feed.error, ZayaAccent.red)
            }
        }

        LazyColumn(
            Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (feed.summary.isNotBlank()) {
                item { Note(feed.summary, ZayaAccent.muted) }
            }
            if (feed.rows.isEmpty()) {
                item {
                    EmptyNote(
                        "Nothing to show yet. The laptop answers this view — WhatsApp " +
                            "itself is never opened from the phone.",
                    )
                }
            }
            items(feed.rows, key = { "${it.chatId}:${it.summary.hashCode()}" }) { row ->
                SectionCard(
                    title = row.title.ifBlank { row.chatId.ifBlank { "WhatsApp" } },
                    subtitle = row.category.ifBlank { row.chatId },
                ) {
                    if (row.reason.isNotBlank() || row.summary.isNotBlank()) {
                        UntrustedQuote(row.reason.ifBlank { row.summary })
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        if (row.score > 0) {
                            StatusChip(
                                text = "score ${row.score}",
                                color = if (row.score >= 60) ZayaAccent.red else ZayaAccent.amber,
                            )
                            Spacer(Modifier.width(8.dp))
                        }
                        OutlinedButton(
                            onClick = {
                                selected = row
                                scope.launch { runtime.whatsapp("conversation", chat = row.chatId) }
                            },
                        ) { Text("Open") }
                    }
                    val open = selected
                    if (open != null && open.chatId == row.chatId) {
                        Spacer(Modifier.height(10.dp))
                        Text(
                            text = "This chat",
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Spacer(Modifier.height(6.dp))
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            for (mode in Protocol.WhatsappMode.PER_CHAT) {
                                OutlinedToggle(
                                    label = mode,
                                    active = feed.chatMode == mode && feed.chatId == row.chatId,
                                    onClick = {
                                        scope.launch { runtime.setWhatsappMode(row.chatId, mode) }
                                    },
                                )
                            }
                        }
                        Text(
                            text = "Changing a chat's mode is the owner's decision and is " +
                                "applied on the laptop, not here.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 6.dp),
                        )
                    }
                }
            }
            if (feed.evidence.isNotEmpty()) {
                item {
                    SectionCard(title = "Evidence", subtitle = "What the laptop based this on") {
                        for (line in feed.evidence) {
                            Text(
                                text = "• $line",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}
