package com.zaya.companion.ui

import android.os.Bundle
import android.content.Intent
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.LaunchedEffect
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
        if (android.os.Build.VERSION.SDK_INT >= 27) {
            setShowWhenLocked(true)
            setTurnScreenOn(true)
        } else {
            @Suppress("DEPRECATION")
            window.addFlags(android.view.WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or
                android.view.WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON)
        }
        ZayaService.ensureRunning(this)
        setContent {
            ZayaTheme {
                val runtime by ZayaApp.runtime.collectAsStateWithLifecycle()
                val current = runtime
                if (current == null) {
                    androidx.compose.material3.Text("Connecting to Zaya…")
                } else {
                    LaunchedEffect(current) {
                        if (intent.action == ZayaService.ACTION_ANSWER) {
                            current.answer(intent.getStringExtra(EXTRA_CALL_ID).orEmpty())
                        }
                    }
                    IncomingCallScreen(runtime = current, onDismiss = { finish() })
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (intent.action == ZayaService.ACTION_ANSWER) {
            ZayaApp.runtime.value?.answer(intent.getStringExtra(EXTRA_CALL_ID).orEmpty())
        }
    }

    companion object {
        const val EXTRA_CALL_ID = "call_id"
    }
}
