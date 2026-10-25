package com.zaya.companion.ui

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import com.zaya.companion.service.ScreenCaptureManager

/**
 * Transient activity that presents Android's system-level screen capture consent dialog
 * and forwards the approved projection token to [ScreenCaptureManager].
 */
class ScreenCaptureConsentActivity : ComponentActivity() {

    companion object {
        private const val TAG = "ScreenCaptureConsent"

        fun requestConsent(context: Context) {
            val intent = Intent(context, ScreenCaptureConsentActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
        }
    }

    private val captureLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            Log.i(TAG, "Screen capture consent granted by user")
            ScreenCaptureManager.setProjectionConsent(result.resultCode, result.data!!)
            com.zaya.companion.service.ZayaService.request(this,
                com.zaya.companion.service.ZayaService.ACTION_PROJECTION_BEGIN)
        } else {
            Log.w(TAG, "Screen capture consent denied or dismissed by user")
            ScreenCaptureManager.onConsentDenied()
        }
        finish()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val mpm = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as? MediaProjectionManager
        if (mpm == null) {
            Log.e(TAG, "MediaProjectionManager unavailable on this device")
            ScreenCaptureManager.onConsentDenied()
            finish()
            return
        }

        try {
            captureLauncher.launch(mpm.createScreenCaptureIntent())
        } catch (e: Exception) {
            Log.e(TAG, "Failed to launch screen capture consent: ${e.message}")
            ScreenCaptureManager.onConsentDenied()
            finish()
        }
    }
}
