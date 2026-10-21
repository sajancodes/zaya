package com.zaya.companion.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.ZayaApp

/** Only this visible owner decision can confirm an external communication. */
class PhoneActionConsentActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val runtime by ZayaApp.runtime.collectAsStateWithLifecycle()
            val current = runtime
            if (current == null) { LaunchedEffect(Unit) { finish() }; return@setContent }
            val approval by current.phoneApproval.collectAsStateWithLifecycle()
            val item = approval
            val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
                item?.let { current.decidePhoneAction(it.requestId, granted) }
                current.refreshPhonePermissions()
            }
            if (item == null) { LaunchedEffect(Unit) { finish() } }
            else MaterialTheme {
                AlertDialog(onDismissRequest = { current.decidePhoneAction(item.requestId, false); finish() },
                    title = { Text("Zaya needs your approval") }, text = { Text(item.message) },
                    confirmButton = { TextButton(onClick = {
                        if (item.permission != null && item.permission != "android.permission.MEDIA_PROJECTION")
                            launcher.launch(item.permission)
                        else { current.decidePhoneAction(item.requestId, item.permission == null); finish() }
                    }) { Text(if (item.permission == null) "Approve" else "Allow permission") } },
                    dismissButton = { TextButton(onClick = {
                        current.decidePhoneAction(item.requestId, false); finish()
                    }) { Text("Decline") } })
            }
        }
    }
}
