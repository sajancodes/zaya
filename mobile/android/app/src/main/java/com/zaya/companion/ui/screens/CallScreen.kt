package com.zaya.companion.ui.screens

import androidx.compose.foundation.Canvas
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import android.Manifest
import android.content.pm.PackageManager
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.protocol.CallUiState
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.runtime.ZayaModel
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.ui.ZayaFace
import kotlinx.coroutines.delay

/** One continuous phone screen, from ringing through answer to hang-up. */
@Composable
fun CallScreen(runtime: ZayaRuntime, onMinimize: () -> Unit) {
    val call by runtime.model.call.collectAsStateWithLifecycle()
    val visual by runtime.model.visual.collectAsStateWithLifecycle()
    val voice by runtime.model.voice.collectAsStateWithLifecycle()
    val speaker by runtime.speakerphone.collectAsStateWithLifecycle()
    val video by runtime.videoEnabled.collectAsStateWithLifecycle()
    val sharing by runtime.videoSharing.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current
    val cameraPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) runtime.setVideoEnabled(true)
        else runtime.model.setVoice(note = "Camera permission is off. The voice call stays connected.")
    }
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) runtime.setVideoEnabled(false)
        }
        lifecycle.lifecycle.addObserver(observer)
        onDispose { lifecycle.lifecycle.removeObserver(observer); runtime.setVideoEnabled(false) }
    }
    var elapsed by remember { mutableLongStateOf(0L) }
    val ringing = call as? CallUiState.Ringing
    val dialing = call as? CallUiState.Dialing
    val active = call as? CallUiState.Active
    val info = ringing?.call ?: dialing?.call ?: active?.call

    LaunchedEffect(active?.call?.callId) {
        elapsed = 0L
        while (active != null) {
            elapsed = ((System.currentTimeMillis() - active.answeredAt) / 1000).coerceAtLeast(0)
            delay(1000)
        }
    }
    Column(
        Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(
            Color(0xFF593044), Color(0xFF2B2029), Color(0xFF181218),
        ))).safeDrawingPadding().padding(horizontal = 28.dp, vertical = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        TextButton(onClick = onMinimize, modifier = Modifier.align(Alignment.End)) {
            Text(if (call is CallUiState.Idle) "Back" else "Minimize", color = Color(0xFFD2BBC8))
        }
        Spacer(Modifier.height(12.dp))
        Text("Zaya", style = MaterialTheme.typography.displaySmall,
            fontWeight = FontWeight.Light, color = Color.White)
        Spacer(Modifier.height(10.dp))
        Text(when {
            active != null -> String.format(java.util.Locale.ROOT, "%02d:%02d", elapsed / 60, elapsed % 60)
            dialing != null -> "Ringing…"
            ringing != null -> "Incoming call"
            else -> "Call ended"
        }, color = Color(0xFFD2BBC8), style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(12.dp))
        if (ringing != null && info != null) {
            Text(info.detail.ifBlank { info.reason }.take(180),
                color = Color(0xFFF8EAF0), textAlign = TextAlign.Center,
                maxLines = 3, style = MaterialTheme.typography.bodyMedium)
        }
        Box(Modifier.fillMaxWidth().weight(1f)) {
            ZayaFace(
            state = if (active != null && voice.micActive) Protocol.LISTENING else visual.state,
            emotion = visual.emotion,
            modifier = Modifier.fillMaxSize(),
        )
            if (video) PhoneVideoPreview(runtime,
                Modifier.align(Alignment.BottomEnd).size(width = 108.dp, height = 150.dp)
                    .clip(RoundedCornerShape(16.dp)))
            if (video) Text(if (!sharing) "Starting camera…" else "Camera on · sharing live", color = Color.White,
                modifier = Modifier.align(Alignment.BottomStart).padding(8.dp),
                style = MaterialTheme.typography.labelSmall)
        }
        if (voice.note.isNotBlank()) Text(voice.note, color = Color(0xFFFFCB91),
            textAlign = TextAlign.Center, modifier = Modifier.padding(bottom = 16.dp))
        if (active != null) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                PhoneControl(if (voice.muted) "Unmute" else "Mute", PhoneGlyph.MIC,
                    selected = voice.muted) { runtime.setMuted(!voice.muted) }
                PhoneControl("Speaker", PhoneGlyph.SPEAKER,
                    selected = speaker) { runtime.setSpeakerphone(!speaker) }
                PhoneControl(if (video) "Video off" else "Video", PhoneGlyph.VIDEO,
                    selected = video) {
                    if (video) runtime.setVideoEnabled(false)
                    else if (context.checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
                        runtime.setVideoEnabled(true)
                    else cameraPermission.launch(Manifest.permission.CAMERA)
                }
            }
            Spacer(Modifier.height(34.dp))
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
            when {
                ringing != null -> {
                    PhoneControl("Decline", PhoneGlyph.HANGUP, Color(0xFFE34C61)) {
                        runtime.decline(ringing.call.callId)
                    }
                    PhoneControl("Answer", PhoneGlyph.CALL, Color(0xFF36B87B)) {
                        runtime.answer(ringing.call.callId)
                    }
                }
                active != null || dialing != null ->
                    PhoneControl("End call", PhoneGlyph.HANGUP, Color(0xFFE34C61)) { runtime.endCall() }
                else -> PhoneControl("Call Zaya", PhoneGlyph.CALL, Color(0xFF36B87B)) { runtime.startCall() }
            }
        }
        Spacer(Modifier.height(20.dp))
    }
}

private enum class PhoneGlyph { CALL, HANGUP, MIC, SPEAKER, VIDEO }

@Composable
private fun PhoneControl(
    label: String, glyph: PhoneGlyph, tint: Color = Color(0xFF4C3B47),
    selected: Boolean = false, onClick: () -> Unit,
) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        FilledIconButton(onClick = onClick, modifier = Modifier.size(72.dp).semantics { contentDescription = label }, shape = CircleShape,
            colors = IconButtonDefaults.filledIconButtonColors(
                containerColor = if (selected) Color.White else tint,
                contentColor = if (selected) Color(0xFF35202F) else Color.White,
            )) {
            val ink = if (selected) Color(0xFF35202F) else Color.White
            Canvas(Modifier.size(30.dp)) {
                val s = size.width / 30f
                val stroke = 2.2f * s
                fun pt(x: Float, y: Float) = Offset(x*s, y*s)
                when (glyph) {
                    PhoneGlyph.VIDEO -> {
                        drawRoundRect(ink, pt(2f, 7f), Size(17*s, 16*s),
                            androidx.compose.ui.geometry.CornerRadius(3*s), style = Stroke(stroke))
                        val lens = Path().apply {
                            moveTo(19*s,12*s); lineTo(28*s,7*s); lineTo(28*s,23*s)
                            lineTo(19*s,18*s); close()
                        }
                        drawPath(lens, ink, style = Stroke(stroke))
                        if (selected) drawLine(ink, pt(2f, 2f), pt(28f, 28f), stroke)
                    }
                    PhoneGlyph.MIC -> {
                        drawRoundRect(ink, pt(11f, 3f), Size(8*s, 15*s),
                            androidx.compose.ui.geometry.CornerRadius(4*s), style = Stroke(stroke))
                        drawArc(ink, 0f, 180f, false, pt(7f, 7f), Size(16*s, 16*s), style = Stroke(stroke))
                        drawLine(ink, pt(15f, 23f), pt(15f, 28f), stroke, StrokeCap.Round)
                        if (selected) drawLine(ink, pt(3f, 3f), pt(27f, 27f), stroke, StrokeCap.Round)
                    }
                    PhoneGlyph.SPEAKER -> {
                        val path = Path().apply {
                            moveTo(3*s,11*s); lineTo(9*s,11*s); lineTo(16*s,5*s)
                            lineTo(16*s,25*s); lineTo(9*s,19*s); lineTo(3*s,19*s); close()
                        }
                        drawPath(path, ink, style = Stroke(stroke))
                        drawArc(ink, -55f, 110f, false, pt(10f, 3f), Size(18*s,24*s), style = Stroke(stroke))
                    }
                    PhoneGlyph.HANGUP, PhoneGlyph.CALL -> {
                        val path = Path().apply {
                            if (glyph == PhoneGlyph.HANGUP) {
                                moveTo(3*s,19*s); cubicTo(7*s,9*s,23*s,9*s,27*s,19*s)
                                lineTo(21*s,21*s); lineTo(20*s,16*s)
                                cubicTo(17*s,14*s,13*s,14*s,10*s,16*s)
                                lineTo(9*s,21*s); close()
                            } else {
                                moveTo(7*s,3*s); lineTo(12*s,10*s); lineTo(9*s,13*s)
                                cubicTo(10*s,17*s,13*s,20*s,17*s,21*s)
                                lineTo(20*s,18*s); lineTo(27*s,23*s)
                                cubicTo(23*s,34*s,0*s,15*s,3*s,7*s); close()
                            }
                        }
                        drawPath(path, ink, style = Stroke(stroke, cap = StrokeCap.Round))
                    }
                }
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(label, color = Color.White, style = MaterialTheme.typography.labelLarge)
    }
}
