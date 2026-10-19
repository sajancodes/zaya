package com.zaya.companion.service

import android.content.Context
import android.content.Intent
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.os.BatteryManager
import android.os.Build
import android.provider.Settings
import android.util.Log

/**
 * Android device hardware controller for instant actions (Flashlight, Wi-Fi, Bluetooth, Battery, Volume).
 */
class HardwareController(private val context: Context) {

    private val cameraManager by lazy { context.getSystemService(Context.CAMERA_SERVICE) as? CameraManager }
    private val audioManager by lazy { context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager }

    fun setFlashlight(enabled: Boolean): Boolean {
        return try {
            val cm = cameraManager ?: return false
            val cameraId = cm.cameraIdList.firstOrNull() ?: return false
            cm.setTorchMode(cameraId, enabled)
            true
        } catch (e: Exception) {
            Log.e("HardwareController", "Failed to toggle torch: ${e.message}")
            false
        }
    }

    fun openWifiSettings(): Boolean {
        return openIntent(Settings.ACTION_WIFI_SETTINGS)
    }

    fun openBluetoothSettings(): Boolean {
        return openIntent(Settings.ACTION_BLUETOOTH_SETTINGS)
    }

    fun openHotspotSettings(): Boolean {
        return openIntent(Settings.ACTION_WIRELESS_SETTINGS)
    }

    fun openLocationSettings(): Boolean {
        return openIntent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
    }

    fun getBatteryStatus(): Map<String, Any> {
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as? BatteryManager
        val level = bm?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: -1
        val isCharging = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            bm?.getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS) == BatteryManager.BATTERY_STATUS_CHARGING
        } else {
            false
        }
        return mapOf(
            "level" to level,
            "charging" to isCharging,
            "os" to "Android ${Build.VERSION.RELEASE} (SDK ${Build.VERSION.SDK_INT})",
            "model" to "${Build.MANUFACTURER} ${Build.MODEL}",
        )
    }

    fun setMediaVolume(percent: Int): Boolean {
        return try {
            val am = audioManager ?: return false
            val maxVol = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
            val target = ((percent.coerceIn(0, 100) / 100.0f) * maxVol).toInt()
            am.setStreamVolume(AudioManager.STREAM_MUSIC, target, 0)
            true
        } catch (e: Exception) {
            false
        }
    }

    private fun openIntent(action: String): Boolean {
        return try {
            val intent = Intent(action).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e("HardwareController", "Could not launch $action: ${e.message}")
            false
        }
    }
}
