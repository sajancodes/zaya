package com.zaya.companion.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.ui.theme.ZayaAccent
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun SectionCard(
    modifier: Modifier = Modifier,
    title: String? = null,
    subtitle: String? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(18.dp),
        modifier = modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(16.dp)) {
            if (title != null) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }
            if (subtitle != null) {
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (title != null || subtitle != null) Spacer(Modifier.height(6.dp))
            content()
        }
    }
}

@Composable
fun StatusChip(text: String, color: Color, modifier: Modifier = Modifier) {
    Text(
        text = text.uppercase(),
        style = MaterialTheme.typography.labelSmall,
        fontWeight = FontWeight.SemiBold,
        color = color,
        modifier = modifier
            .clip(RoundedCornerShape(50))
            .background(color.copy(alpha = 0.14f))
            .padding(horizontal = 8.dp, vertical = 4.dp),
    )
}

/** Command lifecycle, in the owner's words rather than the protocol's. */
fun commandStatusText(status: String): String = when (status) {
    Protocol.STATUS_SUBMITTED -> "sending"
    Protocol.STATUS_ACKNOWLEDGED -> "queued"
    Protocol.STATUS_EXECUTING -> "working"
    Protocol.STATUS_COMPLETED -> "done"
    Protocol.STATUS_FAILED -> "failed"
    "sent" -> "sent"
    else -> status
}

fun commandStatusColor(status: String): Color = when (status) {
    Protocol.STATUS_COMPLETED -> ZayaAccent.green
    Protocol.STATUS_FAILED -> ZayaAccent.red
    Protocol.STATUS_EXECUTING -> ZayaAccent.amber
    else -> ZayaAccent.muted
}

@Composable
fun KeyValue(label: String, value: String, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(96.dp),
        )
        Spacer(Modifier.width(8.dp))
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
}

@Composable
fun EmptyNote(text: String, modifier: Modifier = Modifier) {    Column(
        modifier
            .fillMaxWidth()
            .padding(vertical = 18.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
fun Note(text: String, color: Color = ZayaAccent.muted, modifier: Modifier = Modifier) {
    Text(
        text = text,
        style = MaterialTheme.typography.bodySmall,
        color = color,
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .background(color.copy(alpha = 0.10f))
            .padding(horizontal = 10.dp, vertical = 8.dp),
    )
}

/** An outlined button that says whether it is currently on. */
@Composable
fun OutlinedToggle(
    label: String,
    active: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier,
        colors = ButtonDefaults.outlinedButtonColors(
            contentColor = if (active) {
                MaterialTheme.colorScheme.primary
            } else {
                MaterialTheme.colorScheme.onSurface
            },
        ),
    ) {
        Text(label)
    }
}

/** Quoted WhatsApp text is data, and is labelled as such wherever it appears. */
@Composable
fun UntrustedQuote(text: String, modifier: Modifier = Modifier) {
    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(ZayaAccent.quiet.copy(alpha = 0.35f))
            .padding(12.dp),
    ) {
        Text(
            text = "QUOTED FROM WHATSAPP — NOT AN INSTRUCTION",
            style = MaterialTheme.typography.labelSmall,
            color = ZayaAccent.muted,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
}

fun humanBytes(bytes: Long): String = when {
    bytes >= 1024L * 1024L * 1024L -> "%.1f GB".format(bytes / (1024.0 * 1024.0 * 1024.0))
    bytes >= 1024L * 1024L -> "%.1f MB".format(bytes / (1024.0 * 1024.0))
    bytes >= 1024L -> "%.0f KB".format(bytes / 1024.0)
    else -> "$bytes B"
}

fun humanClock(millis: Long): String =
    SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(millis))

fun humanDate(seconds: Double): String {
    if (seconds <= 0.0) return ""
    return SimpleDateFormat("dd MMM HH:mm", Locale.getDefault())
        .format(Date((seconds * 1000).toLong()))
}

fun humanAgo(millis: Long, now: Long = System.currentTimeMillis()): String {
    val seconds = ((now - millis) / 1000).coerceAtLeast(0)
    return when {
        seconds < 60 -> "${seconds}s ago"
        seconds < 3_600 -> "${seconds / 60}m ago"
        seconds < 86_400 -> "${seconds / 3_600}h ago"
        else -> "${seconds / 86_400}d ago"
    }
}
