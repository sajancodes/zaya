package com.zaya.companion.audio

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Matrix
import android.hardware.camera2.*
import android.hardware.display.DisplayManager
import android.media.ImageReader
import android.os.Handler
import android.os.HandlerThread
import android.view.Surface
import android.view.Display
import android.util.Log
import java.io.ByteArrayOutputStream

/** Front-camera JPEG samples at one frame/second; never writes to disk. */
class PhoneCamera(
    private val context: Context,
    private val onFrame: (ByteArray, Bitmap) -> Unit,
    private val onError: (String) -> Unit,
) {
    private var thread: HandlerThread? = null
    private var handler: Handler? = null
    private var camera: CameraDevice? = null
    private var session: CameraCaptureSession? = null
    private var reader: ImageReader? = null
    @Volatile private var closed = true
    private var orientation = 0

    @SuppressLint("MissingPermission")
    fun start() {
        if (!closed) return
        closed = false
        val worker = HandlerThread("zaya-phone-camera").also { it.start() }
        thread = worker
        val callback = Handler(worker.looper)
        handler = callback
        try {
            val manager = context.getSystemService(CameraManager::class.java)
            val id = manager.cameraIdList.firstOrNull {
                manager.getCameraCharacteristics(it).get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_FRONT
            } ?: manager.cameraIdList.firstOrNull() ?: throw IllegalStateException("No camera is available")
            val info = manager.getCameraCharacteristics(id)
            val rotation = context.getSystemService(DisplayManager::class.java)
                .getDisplay(Display.DEFAULT_DISPLAY)?.rotation ?: Surface.ROTATION_0
            val degrees = when (rotation) { Surface.ROTATION_90 -> 90; Surface.ROTATION_180 -> 180; Surface.ROTATION_270 -> 270; else -> 0 }
            val front = info.get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_FRONT
            orientation = ((info.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 0) +
                (if (front) degrees else -degrees) + 360) % 360
            val sizes = info.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
                ?.getOutputSizes(ImageFormat.JPEG)?.filter { it.width <= 1280 && it.height <= 960 }
                ?: emptyList()
            val size = sizes.minByOrNull { kotlin.math.abs(it.width * it.height - 640 * 480) }
                ?: throw IllegalStateException("No suitable camera resolution")
            val images = ImageReader.newInstance(size.width, size.height, ImageFormat.JPEG, 2)
            reader = images
            images.setOnImageAvailableListener({ source ->
                val image = runCatching { source.acquireLatestImage() }.getOrNull() ?: return@setOnImageAvailableListener
                try {
                    if (closed) return@setOnImageAvailableListener
                    val buffer = image.planes[0].buffer
                    val bytes = ByteArray(buffer.remaining()).also { buffer.get(it) }
                    val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size) ?: return@setOnImageAvailableListener
                    val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height,
                        Matrix().apply { postRotate(orientation.toFloat()) }, true)
                    val scale = minOf(1f, 640f / maxOf(rotated.width, rotated.height))
                    val preview = Bitmap.createScaledBitmap(rotated,
                        (rotated.width * scale).toInt().coerceAtLeast(1),
                        (rotated.height * scale).toInt().coerceAtLeast(1), true)
                    val jpeg = ByteArrayOutputStream().use { stream ->
                        preview.compress(Bitmap.CompressFormat.JPEG, 55, stream)
                        stream.toByteArray()
                    }
                    if (!closed && jpeg.size <= 180000) onFrame(jpeg, preview)
                } catch (_: Exception) {
                    if (!closed) fail("Camera frame unavailable")
                } finally { image.close() }
            }, callback)
            manager.openCamera(id, object : CameraDevice.StateCallback() {
                override fun onOpened(device: CameraDevice) {
                    if (closed) { device.close(); return }
                    camera = device
                    @Suppress("DEPRECATION")
                    device.createCaptureSession(listOf(images.surface), object : CameraCaptureSession.StateCallback() {
                        override fun onConfigured(ready: CameraCaptureSession) {
                            if (closed) { ready.close(); return }
                            session = ready
                            callback.post(capture)
                        }
                        override fun onConfigureFailed(failed: CameraCaptureSession) {
                            if (!closed) fail("Camera could not start")
                        }
                    }, callback)
                }
                override fun onDisconnected(device: CameraDevice) { device.close(); if (!closed) fail("Camera disconnected") }
                override fun onError(device: CameraDevice, error: Int) { device.close(); if (!closed) fail("Camera unavailable") }
            }, callback)
        } catch (error: Exception) {
            Log.w("ZayaCamera", "Camera could not start", error)
            fail("Camera unavailable. Check camera permission and privacy settings.")
        }
    }

    private val capture = object : Runnable {
        override fun run() {
            if (closed) return
            try {
                val device = camera ?: return
                val target = reader?.surface ?: return
                val request = device.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE).apply {
                    addTarget(target)
                    set(CaptureRequest.JPEG_ORIENTATION, 0)
                    set(CaptureRequest.JPEG_QUALITY, 65.toByte())
                    set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_AUTO)
                }.build()
                session?.capture(request, null, handler)
                handler?.postDelayed(this, 1000)
            } catch (_: Exception) { if (!closed) fail("Camera capture stopped") }
        }
    }

    private fun fail(message: String) { stop(); onError(message) }

    fun stop() {
        closed = true
        handler?.removeCallbacksAndMessages(null)
        runCatching { session?.close() }; session = null
        runCatching { camera?.close() }; camera = null
        runCatching { reader?.close() }; reader = null
        thread?.quitSafely(); thread = null; handler = null
    }
}
