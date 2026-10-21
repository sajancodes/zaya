package com.zaya.companion

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import com.zaya.companion.service.ZayaService
import com.zaya.companion.ui.ZayaRoot
import com.zaya.companion.ui.theme.ZayaTheme

/**
 * The app's one window. It holds no state worth keeping: the runtime lives in
 * [ZayaService] so closing this screen does not close Zaya.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        ZayaService.ensureRunning(this)
        setContent {
            ZayaTheme {
                AskForPermissions()
                ZayaRoot()
            }
        }
    }

    override fun onResume() {
        super.onResume()
        ZayaApp.runtime.value?.let { runtime ->
            runtime.refreshPhonePermissions()
            if (runtime.phoneApproval.value != null) startActivity(Intent(this,
                com.zaya.companion.ui.PhoneActionConsentActivity::class.java))
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        ZayaService.ensureRunning(this)
    }

    companion object {
        const val EXTRA_OPEN = "open"
    }
}

/**
 * Voice and notifications are the two permissions the phone genuinely needs.
 * Both are asked for once, in context, and a refusal is survivable: chat, tasks,
 * files and WhatsApp views all work without them.
 */
@Composable
private fun AskForPermissions() {
    val context = LocalContext.current
    val launcher = androidx.activity.compose.rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { }

    LaunchedEffect(Unit) {
        val wanted = buildList {
            if (!granted(context, Manifest.permission.RECORD_AUDIO)) {
                add(Manifest.permission.RECORD_AUDIO)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                !granted(context, Manifest.permission.POST_NOTIFICATIONS)
            ) {
                add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
        if (wanted.isNotEmpty()) launcher.launch(wanted.toTypedArray())
    }
}

private fun granted(context: android.content.Context, permission: String): Boolean =
    ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED
