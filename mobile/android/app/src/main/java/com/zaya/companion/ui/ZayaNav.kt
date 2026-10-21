package com.zaya.companion.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.material3.TextButton
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.ZayaApp
import com.zaya.companion.protocol.CallUiState
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.ui.screens.CallScreen
import com.zaya.companion.ui.screens.ChatScreen
import com.zaya.companion.ui.screens.FilesScreen
import com.zaya.companion.ui.screens.HomeScreen
import com.zaya.companion.ui.screens.IncomingCallScreen
import com.zaya.companion.ui.screens.NotificationsScreen
import com.zaya.companion.ui.screens.SettingsScreen
import com.zaya.companion.ui.screens.TasksScreen
import com.zaya.companion.ui.screens.WhatsappScreen

enum class ZayaScreen(val label: String, val icon: ImageVector) {
    HOME("Home", Icons.Filled.Home),
    CHAT("Chat", Icons.Filled.Email),
    TASKS("Tasks", Icons.AutoMirrored.Filled.List),
    WHATSAPP("Alerts", Icons.Filled.Notifications),
    FILES("Files", Icons.Filled.Share),
    SETTINGS("Settings", Icons.Filled.Settings),
    CALL("Call", Icons.Filled.Home),
    NOTIFICATIONS("Inbox", Icons.Filled.Notifications),
}

/**
 * The whole UI: one runtime, six places to stand.
 *
 * Zaya comes first — the home screen is her face — and an incoming call takes the
 * screen exactly like a phone call would, because that is what it is.
 */
@Composable
fun ZayaRoot() {
    val runtime by ZayaApp.runtime.collectAsStateWithLifecycle()
    val current = runtime
    if (current == null) {
        StartingScreen()
    } else {
        ZayaScaffold(current)
    }
}

@Composable
private fun StartingScreen() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text(
            text = "Starting Zaya…",
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun ZayaScaffold(runtime: ZayaRuntime) {
    var screenName by rememberSaveable { mutableStateOf(ZayaScreen.HOME.name) }
    val call by runtime.model.call.collectAsStateWithLifecycle()
    LaunchedEffect(call) {
        if (call !is CallUiState.Idle) screenName = ZayaScreen.CALL.name
    }
    if (screenName == ZayaScreen.CALL.name) {
        CallScreen(runtime) { screenName = ZayaScreen.HOME.name }
        return
    }

    val screen = runCatching { ZayaScreen.valueOf(screenName) }.getOrDefault(ZayaScreen.HOME)

    Scaffold(
        topBar = {
            if (call !is CallUiState.Idle) TextButton(onClick = { screenName = ZayaScreen.CALL.name }) {
                Text("Return to call with Zaya")
            }
        },
        containerColor = MaterialTheme.colorScheme.background,
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                for (item in listOf(
                    ZayaScreen.HOME,
                    ZayaScreen.CHAT,
                    ZayaScreen.TASKS,
                    ZayaScreen.SETTINGS,
                )) {
                    NavigationBarItem(
                        selected = screen == item || (item == ZayaScreen.SETTINGS &&
                            screen in listOf(ZayaScreen.FILES, ZayaScreen.WHATSAPP)),
                        onClick = { screenName = item.name },
                        icon = { Icon(item.icon, contentDescription = item.label) },
                        label = { Text(item.label) },
                    )
                }
            }
        },
    ) { padding ->
        Box(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            when (screen) {
                ZayaScreen.HOME -> HomeScreen(
                    runtime = runtime,
                    onOpenNotifications = { screenName = ZayaScreen.NOTIFICATIONS.name },
                    onOpenSettings = { screenName = ZayaScreen.SETTINGS.name },
                )

                ZayaScreen.CHAT -> ChatScreen(runtime) { screenName = ZayaScreen.HOME.name }
                ZayaScreen.TASKS -> TasksScreen(runtime) { screenName = ZayaScreen.HOME.name }
                ZayaScreen.WHATSAPP -> WhatsappScreen(runtime) { screenName = ZayaScreen.SETTINGS.name }
                ZayaScreen.FILES -> FilesScreen(runtime) { screenName = ZayaScreen.SETTINGS.name }
                ZayaScreen.SETTINGS -> SettingsScreen(runtime,
                    onBack = { screenName = ZayaScreen.HOME.name },
                    onOpenFiles = { screenName = ZayaScreen.FILES.name },
                    onOpenWhatsapp = { screenName = ZayaScreen.WHATSAPP.name })
                ZayaScreen.NOTIFICATIONS -> NotificationsScreen(runtime) {
                    screenName = ZayaScreen.HOME.name
                }

                ZayaScreen.CALL -> CallScreen(runtime) { screenName = ZayaScreen.HOME.name }
            }
        }
    }
}
