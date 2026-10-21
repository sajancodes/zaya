package com.zaya.companion.ui.screens

import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.material3.TextButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.core.ZayaBuild
import com.zaya.companion.net.AuthResult
import com.zaya.companion.protocol.ConnectionPhase
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.service.ZayaService
import com.zaya.companion.ui.ConnectionDetail
import com.zaya.companion.ui.ConnectionPill
import com.zaya.companion.ui.KeyValue
import com.zaya.companion.ui.Note
import com.zaya.companion.ui.OutlinedToggle
import com.zaya.companion.ui.SectionCard
import com.zaya.companion.ui.theme.ZayaAccent
import kotlinx.coroutines.launch

/**
 * Pairing, and the few switches that belong to the owner.
 *
 * The only secret involved is the one-time key from the laptop's Remote Control
 * panel; the device credential that replaces it is sealed with the Android
 * Keystore and is never typed, shown or backed up.
 */
@Composable
fun SettingsScreen(runtime: ZayaRuntime, onBack: () -> Unit,
                   onOpenFiles: () -> Unit = {}, onOpenWhatsapp: () -> Unit = {}) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val pairing by runtime.pairing.collectAsStateWithLifecycle()
    val status by runtime.connection.collectAsStateWithLifecycle()
    val output by runtime.model.outputTarget.collectAsStateWithLifecycle()
    val serverName by runtime.model.serverName.collectAsStateWithLifecycle()

    var address by remember(pairing) { mutableStateOf(pairing?.address ?: "") }
    var key by remember { mutableStateOf("") }
    var deviceName by remember { mutableStateOf(pairing?.deviceName?.ifBlank { Build.MODEL } ?: Build.MODEL) }
    var message by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
    ) {
        ScreenHeader("Settings", "Make Zaya feel at home", onBack)
        if (message.isNotBlank()) {
            Note(message, ZayaAccent.amber)
            Spacer(Modifier.height(12.dp))
        }

        SectionCard(title = "Your space", subtitle = "Shared content and message controls") {
            TextButton(onClick = onOpenFiles, modifier = Modifier.fillMaxWidth()) { Text("Files & downloads") }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            TextButton(onClick = onOpenWhatsapp, modifier = Modifier.fillMaxWidth()) { Text("WhatsApp & alerts") }
        }
        Spacer(Modifier.height(12.dp))

        SettingsGroup(title = "Laptop connection", subtitle = "Status, reconnect and background activity") {
            Row(verticalAlignment = Alignment.CenterVertically) {
                ConnectionPill(status)
                Spacer(Modifier.padding(horizontal = 4.dp))
            }
            Spacer(Modifier.height(8.dp))
            KeyValue("Server", serverName)
            KeyValue("Address", pairing?.address ?: "not paired")
            KeyValue("Device", pairing?.deviceId?.take(12) ?: "—")
            KeyValue("Protocol", "v${Protocol.VERSION} · app ${ZayaBuild.VERSION}")
            ConnectionDetail(status)
            if (status.phase == ConnectionPhase.INCOMPATIBLE) {
                Spacer(Modifier.height(8.dp))
                Note(
                    "This app and the laptop disagree about the protocol version. Update " +
                        "whichever is older; nothing else will fix this.",
                    ZayaAccent.red,
                )
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { runtime.reconnectNow() }) { Text("Reconnect") }
                OutlinedButton(
                    onClick = {
                        runtime.stop()
                        ZayaService.request(context, ZayaService.ACTION_DISCONNECT)
                        message = "Background link stopped."
                    },
                ) { Text("Stop background") }
            }
        }

        Spacer(Modifier.height(12.dp))
        SettingsGroup(
            title = if (pairing == null) "Pair with your laptop" else "Pair a different laptop",
            subtitle = "On the laptop: Zaya's Settings & Controls → Remote Control → the 6-character key",
            initiallyExpanded = pairing == null,
        ) {
            OutlinedTextField(
                value = address,
                onValueChange = { address = it },
                label = { Text("Laptop address") },
                placeholder = { Text("laptop.tailnet.ts.net:8000") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = key,
                onValueChange = { key = it.take(12) },
                label = { Text("Pairing key") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = deviceName,
                onValueChange = { deviceName = it.take(60) },
                label = { Text("Name for this phone") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(10.dp))
            Button(
                onClick = {
                    busy = true
                    message = ""
                    scope.launch {
                        val result = runtime.pair(address, key, deviceName)
                        message = when (result) {
                            is AuthResult.Ok -> "Paired with ${result.serverName}."
                            is AuthResult.Denied -> result.message
                            is AuthResult.Unavailable -> result.message
                        }
                        if (result is AuthResult.Ok) key = ""
                        busy = false
                    }
                },
                enabled = !busy && address.isNotBlank() && key.isNotBlank(),
            ) { Text(if (busy) "Pairing…" else "Pair") }
            Spacer(Modifier.height(6.dp))
            Text(
                text = "Use the name Tailscale gives the laptop, for example " +
                    "laptop.tailnet.ts.net:8000. Plain HTTP is allowed only inside " +
                    "your tailnet; anything else needs HTTPS.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        Spacer(Modifier.height(12.dp))
        SettingsGroup(
            title = "Where Zaya's voice comes out",
            subtitle = "During a call the laptop routes her voice here automatically",
        ) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedToggle(
                    label = "Laptop",
                    active = output == Protocol.Output.DESKTOP,
                    onClick = { runtime.changeOutputInBackground(Protocol.Output.DESKTOP) },
                )
                OutlinedToggle(
                    label = "Phone",
                    active = output == Protocol.Output.PHONE,
                    onClick = { runtime.changeOutputInBackground(Protocol.Output.PHONE) },
                )
                OutlinedToggle(
                    label = "Both",
                    active = output == Protocol.Output.BOTH,
                    onClick = { runtime.changeOutputInBackground(Protocol.Output.BOTH) },
                )
            }
        }

        Spacer(Modifier.height(12.dp))
        UpdateCard(runtime)

        Spacer(Modifier.height(12.dp))
        CallPermissionCard()

        Spacer(Modifier.height(12.dp))
        SettingsGroup(title = "About & privacy", subtitle = "This phone, your data and linked devices") {
            KeyValue("Microphone", "only while you are in a call")
            KeyValue("Created by", "Sajan Rai")
            KeyValue("Secrets", "device credential sealed with the Android Keystore")
            Spacer(Modifier.height(10.dp))
            if (pairing != null) {
                OutlinedButton(
                    onClick = {
                        scope.launch {
                            val revoked = runtime.forgetDevice()
                            message = if (revoked) {
                                "Removed from the laptop and forgotten here."
                            } else {
                                "Forgotten here. Revoke it on the laptop too if it is not listed."
                            }
                        }
                    },
                ) { Text("Forget this laptop") }
            }
        }

        Spacer(Modifier.height(12.dp))
        Note(
            "Nothing on this phone holds a copy of Zaya's memory, her tools or her " +
                "WhatsApp session: it renders what the laptop sends and forwards your " +
                "voice and text to it.",
        )
        Spacer(Modifier.height(32.dp))
    }
}

@Composable
private fun SettingsGroup(title: String, subtitle: String = "", initiallyExpanded: Boolean = false,
                          content: @Composable ColumnScope.() -> Unit) {
    var expanded by rememberSaveable { mutableStateOf(initiallyExpanded) }
    SectionCard {
        TextButton(onClick = { expanded = !expanded }, modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.Start) {
                Text(title, style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface)
                if (subtitle.isNotBlank()) Text(subtitle, style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(Icons.Filled.ArrowDropDown, modifier = Modifier.rotate(if (expanded) 180f else 0f),
                contentDescription = if (expanded) "Collapse $title" else "Expand $title")
        }
        if (expanded) {
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}

/**
 * Android 14 and newer let the owner (or the system) revoke "take over the
 * screen" — the switch that turns a ringing call into a full-screen window
 * instead of a heads-up notification. It lives in system settings, so the app
 * can only point at it, never grant it.
 */
@Composable
fun CallPermissionCard(compact: Boolean = false, onConfigure: () -> Unit = {}) {
    val context = LocalContext.current
    var allowed by remember { mutableStateOf(canTakeOverScreen(context)) }
    var overApps by remember { mutableStateOf(Settings.canDrawOverlays(context)) }
    var notifications by remember { mutableStateOf(callNotificationsAllowed(context)) }
    var ringing by remember { mutableStateOf(phoneRings(context)) }
    val owner = LocalLifecycleOwner.current
    DisposableEffect(owner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                allowed = canTakeOverScreen(context)
                overApps = Settings.canDrawOverlays(context)
                notifications = callNotificationsAllowed(context)
                ringing = phoneRings(context)
            }
        }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer) }
    }
    if (allowed && overApps && notifications && ringing) return
    if (compact) {
        OutlinedButton(onClick = onConfigure, modifier = Modifier.fillMaxWidth()) {
            Text("Finish setting up ringing calls")
        }
        return
    }
    SectionCard(title = "Set up incoming calls",
        subtitle = "Answer and decline on screen, with a repeating ringtone") {
        if (!notifications) {
            Text("Call notifications are off or quiet.")
            Button(onClick = {
                runCatching { context.startActivity(Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)) }
            }) { Text("Allow call notifications") }
        }
        if (!allowed) {
            Text("Allow full-screen calls to wake the locked screen.")
            Button(onClick = { openTakeOverSettings(context) }) { Text("Allow full-screen calls") }
        }
        if (!overApps) {
            Text("Allow Zaya to show the call screen above other apps.")
            Button(onClick = {
                runCatching { context.startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:${context.packageName}"))) }
            }) { Text("Allow calls over other apps") }
        }
        if (!ringing) {
            Text("Your phone is in silent or vibrate mode. Calls respect that setting.")
            Button(onClick = { runCatching { context.startActivity(Intent(Settings.ACTION_SOUND_SETTINGS)) } }) {
                Text("Ringtone and volume")
            }
        }
    }
}

private fun phoneRings(context: Context): Boolean =
    context.getSystemService(android.media.AudioManager::class.java)?.ringerMode ==
        android.media.AudioManager.RINGER_MODE_NORMAL

private fun callNotificationsAllowed(context: Context): Boolean {
    val manager = context.getSystemService(NotificationManager::class.java) ?: return false
    val channel = manager.getNotificationChannel(com.zaya.companion.service.Notifications.CHANNEL_CALLS)
    return manager.areNotificationsEnabled() &&
        (channel == null || channel.importance >= NotificationManager.IMPORTANCE_HIGH)
}

private fun canTakeOverScreen(context: Context): Boolean {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.UPSIDE_DOWN_CAKE) return true
    val manager = context.getSystemService(NotificationManager::class.java) ?: return true
    return runCatching { manager.canUseFullScreenIntent() }.getOrDefault(true)
}

private fun openTakeOverSettings(context: Context) {
    val fallback = Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
        .putExtra(Settings.EXTRA_APP_PACKAGE, context.packageName)
        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
        Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT)
            .setData(Uri.parse("package:${context.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    } else {
        fallback
    }
    runCatching { context.startActivity(intent) }
        .onFailure { runCatching { context.startActivity(fallback) } }
}
