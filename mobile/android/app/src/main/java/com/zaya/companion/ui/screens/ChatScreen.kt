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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.protocol.ChatLine
import com.zaya.companion.protocol.Speaker
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.ui.StatusChip
import com.zaya.companion.ui.commandStatusColor
import com.zaya.companion.ui.commandStatusText
import com.zaya.companion.ui.humanClock
import com.zaya.companion.ui.theme.ZayaAccent

/**
 * The transcript, including the one thing the dashboard never showed: what
 * happened to each command the owner sent from this phone.
 */
@Composable
fun ChatScreen(runtime: ZayaRuntime, onBack: () -> Unit) {
    val lines by runtime.model.chat.collectAsStateWithLifecycle()
    val status by runtime.connection.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()

    LaunchedEffect(lines.size) {
        if (lines.isNotEmpty()) listState.animateScrollToItem(lines.lastIndex)
    }

    Column(Modifier.fillMaxSize()) {
        Box(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
            ScreenHeader(
                title = "Chat",
                subtitle = if (status.isOnline) "Live with your laptop" else status.detail,
                onBack = onBack,
            )
        }
        LazyColumn(
            state = listState,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(lines, key = { it.id }) { line -> ChatBubble(line) }
        }
        Box(Modifier.padding(16.dp)) {
            CommandInput(runtime)
        }
    }
}

@Composable
private fun ChatBubble(line: ChatLine) {
    val alignment = when (line.speaker) {
        Speaker.OWNER -> Alignment.End
        Speaker.NOTICE -> Alignment.CenterHorizontally
        Speaker.ZAYA -> Alignment.Start
    }
    val background = when (line.speaker) {
        Speaker.OWNER -> MaterialTheme.colorScheme.primary.copy(alpha = 0.20f)
        Speaker.ZAYA -> MaterialTheme.colorScheme.surface
        Speaker.NOTICE -> ZayaAccent.quiet.copy(alpha = 0.35f)
    }
    Column(Modifier.fillMaxWidth(), horizontalAlignment = alignment) {
        Box(
            Modifier
                .widthIn(max = 320.dp)
                .clip(RoundedCornerShape(16.dp))
                .background(background)
                .padding(horizontal = 14.dp, vertical = 10.dp),
        ) {
            Text(
                text = line.text,
                style = MaterialTheme.typography.bodyLarge,
                fontStyle = if (line.speaker == Speaker.NOTICE) FontStyle.Italic else FontStyle.Normal,
                color = MaterialTheme.colorScheme.onSurface,
            )
        }
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(top = 2.dp, start = 6.dp, end = 6.dp),
        ) {
            Text(
                text = humanClock(line.at),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (line.status.isNotBlank()) {
                Spacer(Modifier.width(6.dp))
                when (line.status) {
                    "sending", "sent" -> Text(
                        text = commandStatusText(line.status),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )

                    else -> {
                        if (line.status !in setOf("done", "failed")) {
                            CircularProgressIndicator(
                                strokeWidth = 1.5.dp,
                                modifier = Modifier.width(10.dp).height(10.dp),
                                color = commandStatusColor(line.status),
                            )
                            Spacer(Modifier.width(4.dp))
                        }
                        StatusChip(
                            text = commandStatusText(line.status),
                            color = commandStatusColor(line.status),
                        )
                    }
                }
            }
        }
        if (line.error.isNotBlank()) {
            Text(
                text = line.error,
                style = MaterialTheme.typography.bodySmall,
                color = ZayaAccent.red,
                modifier = Modifier.padding(top = 2.dp, start = 6.dp, end = 6.dp),
            )
        }
    }
}
