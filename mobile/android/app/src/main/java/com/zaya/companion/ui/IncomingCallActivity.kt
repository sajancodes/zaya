package com.zaya.companion.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.ZayaApp
import com.zaya.companion.service.ZayaService
import com.zaya.companion.ui.screens.IncomingCallScreen
import com.zaya.companion.ui.theme.ZayaTheme

/**
 * Zaya calling while the app is closed.
 *
 * The same runtime the service owns feeds this screen; declining or answering
 * goes through the runtime, so this window is a view onto the call, not the call
 * itself. It closes itself the moment the laptop says the call is over.
 */
class IncomingCallActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setShowWhenLocked(true)
        setTurnScreenOn(true)
        ZayaService.ensureRunning(this)
        setContent {
            ZayaTheme {
                val runtime by ZayaApp.runtime.collectAsStateWithLifecycle()
                val current = runtime
                if (current == null) {
                    finish()
                } else {
                    IncomingCallScreen(runtime = current, onDismiss = { finish() })
                }
            }
        }
    }

    companion object {
        const val EXTRA_CALL_ID = "call_id"
    }
}
