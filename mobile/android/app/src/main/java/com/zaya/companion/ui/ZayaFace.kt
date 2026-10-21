package com.zaya.companion.ui

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.zaya.companion.protocol.ConnectionPhase
import com.zaya.companion.protocol.ConnectionStatus
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.ui.theme.ZayaAccent
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Loads whichever face the laptop's state calls for, off the main thread. */
@Composable
fun rememberZayaFace(state: String, emotion: String): ImageBitmap? {
    val context = LocalContext.current
    val art by produceState<ImageBitmap?>(initialValue = null, state, emotion) {
        value = withContext(Dispatchers.IO) { ZayaArt.resolve(context, state, emotion) }
    }
    return art
}

/**
 * Zaya, as the laptop describes her.
 *
 * Only colour, dimming and motion are decided here — the picture itself, and
 * which emotion it shows, comes from the state the laptop sent.
 */
@Composable
fun ZayaFace(
    state: String,
    emotion: String,
    modifier: Modifier = Modifier,
    showOverlay: Boolean = true,
) {
    val art = rememberZayaFace(state, emotion)
    val transition = rememberInfiniteTransition(label = "zaya-face")
    val pulse by transition.animateFloat(
        initialValue = 0.25f,
        targetValue = 0.6f,
        animationSpec = infiniteRepeatable(tween(1400), RepeatMode.Reverse),
        label = "pulse",
    )

    Box(modifier, contentAlignment = Alignment.Center) {
        val glow = when (state) {
            Protocol.LISTENING -> Color(0xFFF4A8C5).copy(alpha = 0.20f)
            Protocol.SPEAKING -> Color(0xFFDDB8D3).copy(alpha = 0.24f)
            Protocol.THINKING -> Color(0xFF22C55E).copy(alpha = 0.16f)
            Protocol.TASK_RUNNING -> Color(0xFF22C55E).copy(alpha = 0.16f)
            Protocol.ERROR -> Color(0xFFEF4444).copy(alpha = 0.26f)
            else -> Color.Transparent
        }
        if (glow != Color.Transparent && showOverlay) {
            Box(
                Modifier
                    .fillMaxSize()
                    .background(
                        Brush.radialGradient(
                            listOf(glow.copy(alpha = glow.alpha * (0.6f + pulse)), Color.Transparent),
                        ),
                    ),
            )
        }
        if (art != null) {
            Image(
                bitmap = art,
                contentDescription = "Zaya is ${state.lowercase()}",
                contentScale = ContentScale.Fit,
                modifier = Modifier
                    .fillMaxSize()
                    .alpha(if (state == Protocol.SLEEPING || state == Protocol.STANDBY) 0.72f else 1f),
            )
        } else {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    text = serverlessHint(state),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(24.dp),
                )
            }
        }
        if (showOverlay && state == Protocol.MUTED) {
            StateBadge("Muted", ZayaAccent.muted, Modifier.align(Alignment.BottomCenter))
        }
        if (showOverlay && state == Protocol.CONNECTING) {
            StateBadge("Connecting", ZayaAccent.amber, Modifier.align(Alignment.BottomCenter))
        }
    }
}

private fun serverlessHint(state: String): String =
    "Zaya's picture is not on this phone yet.\nDrop zaya_neutral.png into " +
        "mobile/android/assets/ (see image.txt).\nState: $state"

@Composable
fun StateBadge(text: String, color: Color, modifier: Modifier = Modifier) {
    Surface(
        color = color.copy(alpha = 0.22f),
        contentColor = MaterialTheme.colorScheme.onSurface,
        shape = RoundedCornerShape(50),
        modifier = modifier.padding(12.dp),
    ) {
        Text(
            text = text.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
        )
    }
}

/** The one line the owner checks before trusting anything else on the screen. */
@Composable
fun ConnectionPill(status: ConnectionStatus, modifier: Modifier = Modifier) {
    val (label, color) = when (status.phase) {
        ConnectionPhase.ONLINE -> "Connected" to ZayaAccent.green
        ConnectionPhase.CONNECTING -> "Connecting" to ZayaAccent.amber
        ConnectionPhase.OFFLINE -> "Offline" to ZayaAccent.red
        ConnectionPhase.UNPAIRED -> "Not paired" to ZayaAccent.muted
        ConnectionPhase.REVOKED -> "Removed" to ZayaAccent.red
        ConnectionPhase.INCOMPATIBLE -> "Version mismatch" to ZayaAccent.red
    }
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = modifier
            .clip(RoundedCornerShape(50))
            .background(color.copy(alpha = 0.14f))
            .border(1.dp, color.copy(alpha = 0.5f), RoundedCornerShape(50))
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        Box(
            Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(color),
        )
        Spacer(Modifier.size(8.dp))
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
}

@Composable
fun ConnectionDetail(status: ConnectionStatus, modifier: Modifier = Modifier) {
    val parts = buildList {
        if (status.detail.isNotBlank()) add(status.detail)
        if (status.retryInSeconds > 0) add("retrying in ${status.retryInSeconds}s")
        if (status.attempts > 1) add("attempt ${status.attempts}")
    }
    Column(modifier) {
        for (part in parts) {
            Text(
                text = part,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
