package com.zaya.companion.ui.screens

import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.protocol.RemoteFile
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.ui.EmptyNote
import com.zaya.companion.ui.Note
import com.zaya.companion.ui.SectionCard
import com.zaya.companion.ui.humanBytes
import com.zaya.companion.ui.humanDate
import com.zaya.companion.ui.theme.ZayaAccent
import kotlinx.coroutines.launch
import java.io.File

/**
 * Files, both ways, through the same folder the dashboard already uses.
 *
 * Uploads land in the laptop's existing uploads directory, so they are visible to
 * Zaya and to the desktop dashboard without a new transfer system; downloads come
 * back into a folder this app owns and can hand to another app.
 */
@Composable
fun FilesScreen(runtime: ZayaRuntime, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val status by runtime.connection.collectAsStateWithLifecycle()
    var remote by remember { mutableStateOf<List<RemoteFile>>(emptyList()) }
    var local by remember { mutableStateOf<List<File>>(emptyList()) }
    var message by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf("") }

    fun refreshLocal() {
        local = runtime.downloadsFolder().listFiles()?.sortedByDescending { it.lastModified() } ?: emptyList()
    }

    LaunchedEffect(status.isOnline) {
        if (!status.isOnline) return@LaunchedEffect
        busy = "Loading…"
        remote = runtime.listFiles()
        refreshLocal()
        busy = ""
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        val name = displayName(context, uri) ?: "upload"
        busy = "Sending $name…"
        scope.launch {
            val ok = runCatching { runtime.upload(uri, name) }.getOrDefault(false)
            message = if (ok) "Sent $name to the laptop." else "Could not send $name."
            if (ok) remote = runtime.listFiles()
            busy = ""
        }
    }

    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
            ScreenHeader("Files", "Shared with your laptop's Zaya", onBack)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(
                    onClick = { picker.launch(arrayOf("*/*")) },
                    enabled = status.isOnline && busy.isEmpty(),
                ) { Text("Send a file") }
                OutlinedButton(
                    onClick = {
                        scope.launch {
                            busy = "Refreshing…"
                            remote = runtime.listFiles()
                            refreshLocal()
                            busy = ""
                        }
                    },
                    enabled = status.isOnline && busy.isEmpty(),
                ) { Text("Refresh") }
            }
            if (busy.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Note(busy, ZayaAccent.amber)
            }
            if (message.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Note(message, ZayaAccent.green)
            }
            if (!status.isOnline) {
                Spacer(Modifier.height(8.dp))
                Note("Offline: files need the laptop.", ZayaAccent.amber)
            }
        }

        LazyColumn(
            Modifier.fillMaxSize(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                SectionCard(title = "On the laptop", subtitle = "Zaya's uploads folder") {
                    if (remote.isEmpty()) {
                        EmptyNote("Nothing there yet.")
                    }
                    for (file in remote) {
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(file.name, style = MaterialTheme.typography.bodyMedium)
                                Text(
                                    text = "${humanBytes(file.size)} · ${humanDate(file.modified)}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            OutlinedButton(
                                onClick = {
                                    busy = "Fetching ${file.name}…"
                                    scope.launch {
                                        val saved = runCatching { runtime.download(file.name) }
                                        message = saved.fold(
                                            onSuccess = { "Saved ${it.name} on this phone." },
                                            onFailure = { it.message ?: "Download failed." },
                                        )
                                        refreshLocal()
                                        busy = ""
                                    }
                                },
                                enabled = busy.isEmpty(),
                            ) { Text("Get") }
                        }
                    }
                }
            }
            item {
                SectionCard(
                    title = "On this phone",
                    subtitle = "Saved by this app — nothing here left the laptop's folder",
                ) {
                    if (local.isEmpty()) {
                        EmptyNote("No files downloaded yet.")
                    }
                    for (file in local) {
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(file.name, style = MaterialTheme.typography.bodyMedium)
                                Text(
                                    text = humanBytes(file.length()),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            OutlinedButton(onClick = { share(context, runtime, file) }) {
                                Text("Share")
                            }
                        }
                    }
                }
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}

private fun displayName(context: android.content.Context, uri: Uri): String? =
    runCatching {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            ?.use { cursor ->
                if (cursor.moveToFirst()) cursor.getString(0) else null
            }
    }.getOrNull()

private fun share(context: android.content.Context, runtime: ZayaRuntime, file: File) {
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
    val send = Intent(Intent.ACTION_SEND)
        .setType("application/octet-stream")
        .putExtra(Intent.EXTRA_STREAM, uri)
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    runCatching { context.startActivity(Intent.createChooser(send, "Share ${file.name}")) }
}
