package com.zaya.companion.service

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.camera2.CameraAccessException
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log

data class FlashlightState(
    val hasFlash: Boolean,
    val isAvailable: Boolean,
    val isOn: Boolean,
    val errorMessage: String? = null,
)

/**
 * Android device hardware controller for instant actions (Flashlight, System Settings, Battery, Volume).
 *
 * Tracks live torch availability and state using [CameraManager.TorchCallback].
 */
class HardwareController(private val context: Context) {

    private val cameraManager by lazy {
        context.getSystemService(Context.CAMERA_SERVICE) as? CameraManager
    }
    private val audioManager by lazy {
        context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
    }

    private val mainHandler = Handler(Looper.getMainLooper())

    @Volatile
    var isFlashlightOn: Boolean = false
        private set

    @Volatile
    var isFlashlightAvailable: Boolean = false
        private set

    private var activeCameraId: String? = null

    init {
        initTorchMonitoring()
    }

    private fun initTorchMonitoring() {
        val cm = cameraManager ?: return
        try {
            val cameraIds = cm.cameraIdList
            activeCameraId = cameraIds.firstOrNull { id ->
                val chars = cm.getCameraCharacteristics(id)
                chars.get(android.hardware.camera2.CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
            } ?: cameraIds.firstOrNull()

            isFlashlightAvailable = activeCameraId != null && hasFlashlightHardware()

            cm.registerTorchCallback(object : CameraManager.TorchCallback() {
                override fun onTorchModeChanged(cameraId: String, enabled: Boolean) {
                    super.onTorchModeChanged(cameraId, enabled)
                    if (cameraId == activeCameraId) {
                        isFlashlightOn = enabled
                        isFlashlightAvailable = true
                    }
                }

                override fun onTorchModeUnavailable(cameraId: String) {
                    super.onTorchModeUnavailable(cameraId)
                    if (cameraId == activeCameraId) {
                        isFlashlightAvailable = false
                        isFlashlightOn = false
                    }
                }
            }, mainHandler)
        } catch (e: Exception) {
            Log.w("HardwareController", "Could not register torch callback: ${e.message}")
        }
    }

    fun hasFlashlightHardware(): Boolean {
        return context.packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_FLASH)
    }

    fun getFlashlightState(): FlashlightState {
        val hasFlash = hasFlashlightHardware()
        if (!hasFlash) {
            return FlashlightState(
                hasFlash = false,
                isAvailable = false,
                isOn = false,
                errorMessage = "This device does not have a camera flash hardware."
            )
        }
        return FlashlightState(
            hasFlash = true,
            isAvailable = isFlashlightAvailable,
            isOn = isFlashlightOn,
            errorMessage = if (!isFlashlightAvailable) "Flashlight is currently in use or unavailable" else null
        )
    }

    fun setFlashlight(enabled: Boolean): Result<Boolean> {
        val hasFlash = hasFlashlightHardware()
        if (!hasFlash) {
            return Result.failure(IllegalStateException("No camera flash hardware detected on this device."))
        }

        val cm = cameraManager ?: return Result.failure(IllegalStateException("Camera service unavailable."))
        val cameraId = activeCameraId ?: return Result.failure(IllegalStateException("No flashlight-capable camera found."))

        return try {
            cm.setTorchMode(cameraId, enabled)
            isFlashlightOn = enabled
            Result.success(enabled)
        } catch (e: CameraAccessException) {
            val reason = when (e.reason) {
                CameraAccessException.CAMERA_IN_USE -> "Camera or flashlight is currently in use by another app."
                CameraAccessException.MAX_CAMERAS_IN_USE -> "Too many camera sessions active."
                CameraAccessException.CAMERA_DISABLED -> "Camera access is disabled by device policy."
                CameraAccessException.CAMERA_DISCONNECTED -> "Camera was disconnected."
                else -> e.message ?: "Camera error."
            }
            Log.e("HardwareController", "CameraAccessException toggling torch: $reason")
            Result.failure(e)
        } catch (e: Exception) {
            Log.e("HardwareController", "Failed to toggle torch: ${e.message}")
            Result.failure(e)
        }
    }

    // ── System Settings Navigation ──────────────────────────────────────────

    fun openWifiSettings(): Boolean = openIntent(Settings.ACTION_WIFI_SETTINGS)

    fun openBluetoothSettings(): Boolean = openIntent(Settings.ACTION_BLUETOOTH_SETTINGS)

    fun openHotspotSettings(): Boolean = openIntent(Settings.ACTION_WIRELESS_SETTINGS)

    fun openLocationSettings(): Boolean = openIntent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)

    fun openDisplaySettings(): Boolean = openIntent(Settings.ACTION_DISPLAY_SETTINGS)

    fun openSoundSettings(): Boolean = openIntent(Settings.ACTION_SOUND_SETTINGS)

    fun openNotificationListenerSettings(): Boolean = openIntent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)

    fun openAppDetailsSettings(packageName: String? = null): Boolean {
        val pkg = packageName ?: context.packageName
        return try {
            val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.fromParts("package", pkg, null)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e("HardwareController", "Could not open app details for $pkg: ${e.message}")
            false
        }
    }

    fun openAppNotificationSettings(packageName: String? = null): Boolean {
        val pkg = packageName ?: context.packageName
        return try {
            val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).apply {
                    putExtra(Settings.EXTRA_APP_PACKAGE, pkg)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
            } else {
                Intent("android.settings.APP_NOTIFICATION_SETTINGS").apply {
                    putExtra("app_package", pkg)
                    putExtra("app_uid", context.applicationInfo.uid)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
            }
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e("HardwareController", "Could not open notification settings for $pkg: ${e.message}")
            false
        }
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
