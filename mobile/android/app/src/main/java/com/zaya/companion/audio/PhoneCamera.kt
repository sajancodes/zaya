package com.zaya.companion.audio

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.*
import android.hardware.camera2.*
import android.hardware.display.DisplayManager
import android.media.ImageReader
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.util.Log
import android.view.Display
import android.view.Surface
import java.io.ByteArrayOutputStream

/** Smooth native preview; at most one bounded image/second goes to Zaya. */
class PhoneCamera(
    private val context: Context,
    private val onFrame: (ByteArray) -> Unit,
    private val onGeometry: (Geometry) -> Unit,
    private val onError: (String) -> Unit,
) {
    data class Geometry(val width: Int, val height: Int, val rotation: Int, val front: Boolean)
    private var thread: HandlerThread? = null
    private var handler: Handler? = null
    private var camera: CameraDevice? = null
    private var session: CameraCaptureSession? = null
    private var reader: ImageReader? = null
    @Volatile private var closed = true
    @Volatile private var opening = false
    private var orientation = 0
    private var lastSample = 0L

    @SuppressLint("MissingPermission")
    fun start(preview: Surface, configurePreview: (Int, Int) -> Unit) {
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
            val streams = info.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
            val previewSizes = streams?.getOutputSizes(SurfaceTexture::class.java)?.toSet() ?: emptySet()
            val sizes = streams?.getOutputSizes(ImageFormat.YUV_420_888)
                ?.filter { it.width <= 1280 && it.height <= 960 && it in previewSizes }
                ?: emptyList()
            val size = sizes.minByOrNull { kotlin.math.abs(it.width * it.height - 640 * 480) }
                ?: throw IllegalStateException("No suitable camera resolution")
            // Buffer geometry must be set synchronously before session creation.
            configurePreview(size.width, size.height)
            onGeometry(Geometry(size.width, size.height, orientation, front))
            val images = ImageReader.newInstance(size.width, size.height, ImageFormat.YUV_420_888, 2)
            reader = images
            images.setOnImageAvailableListener({ source ->
                val image = runCatching { source.acquireLatestImage() }.getOrNull() ?: return@setOnImageAvailableListener
                try {
                    val now = SystemClock.elapsedRealtime()
                    if (closed || now - lastSample < 1000) return@setOnImageAvailableListener
                    lastSample = now
                    val planes = image.planes
                    val nv21 = YuvPlanes.nv21(image.width, image.height,
                        planes[0].buffer, planes[0].rowStride, planes[0].pixelStride,
                        planes[1].buffer, planes[1].rowStride, planes[1].pixelStride,
                        planes[2].buffer, planes[2].rowStride, planes[2].pixelStride)
                    val raw = ByteArrayOutputStream().use { stream ->
                        YuvImage(nv21, ImageFormat.NV21, image.width, image.height, null)
                            .compressToJpeg(Rect(0, 0, image.width, image.height), 65, stream)
                        stream.toByteArray()
                    }
                    val jpeg = orientAndBound(raw) ?: return@setOnImageAvailableListener
                    if (!closed && jpeg.size <= 180000) onFrame(jpeg)
                } catch (error: Exception) {
                    if (!closed) { Log.w("ZayaCamera", "Camera frame unavailable", error); fail("Camera frame unavailable") }
                } finally { runCatching { image.close() } }
            }, callback)
            opening = true
            manager.openCamera(id, object : CameraDevice.StateCallback() {
                override fun onOpened(device: CameraDevice) {
                    opening = false
                    if (closed) { device.close(); releaseOnWorker(); return }
                    camera = device
                    try {
                        @Suppress("DEPRECATION")
                        device.createCaptureSession(listOf(preview, images.surface), object : CameraCaptureSession.StateCallback() {
                            override fun onConfigured(ready: CameraCaptureSession) {
                                if (closed) { ready.close(); return }
                                session = ready
                                try {
                                    val request = device.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW).apply {
                                        addTarget(preview); addTarget(images.surface)
                                        set(CaptureRequest.CONTROL_MODE, CaptureRequest.CONTROL_MODE_AUTO)
                                        val ranges = info.get(CameraCharacteristics.CONTROL_AE_AVAILABLE_TARGET_FPS_RANGES)
                                        ranges?.filter { it.lower >= 15 && it.upper <= 30 }?.maxByOrNull { it.upper }
                                            ?.let { set(CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, it) }
                                    }.build()
                                    ready.setRepeatingRequest(request, null, callback)
                            } catch (error: Exception) { if (!closed) fail("Camera could not start") }
                        }
                        override fun onConfigureFailed(failed: CameraCaptureSession) {
                            failed.close()
                            if (!closed) fail("Camera could not start")
                        }
                    }, callback)
                    } catch (error: Exception) { if (!closed) fail("Camera could not start") }
                }
                override fun onDisconnected(device: CameraDevice) { opening = false; device.close(); if (!closed) fail("Camera disconnected") else releaseOnWorker() }
                override fun onError(device: CameraDevice, error: Int) { opening = false; device.close(); if (!closed) fail("Camera unavailable") else releaseOnWorker() }
            }, callback)
        } catch (error: Exception) {
            opening = false
            Log.w("ZayaCamera", "Camera could not start", error)
            fail("Camera unavailable. Check camera permission and privacy settings.")
        }
    }

    private fun orientAndBound(raw: ByteArray): ByteArray? {
        val decoded = BitmapFactory.decodeByteArray(raw, 0, raw.size) ?: return null
        var rotated: Bitmap? = null
        var scaled: Bitmap? = null
        try {
            val oriented = Bitmap.createBitmap(decoded, 0, 0, decoded.width, decoded.height,
                Matrix().apply { postRotate(orientation.toFloat()) }, true)
            rotated = oriented
            val factor = minOf(1f, 640f / maxOf(oriented.width, oriented.height))
            val bounded = Bitmap.createScaledBitmap(oriented,
                (oriented.width * factor).toInt().coerceAtLeast(1),
                (oriented.height * factor).toInt().coerceAtLeast(1), true)
            scaled = bounded
            return ByteArrayOutputStream().use { stream ->
                if (!bounded.compress(Bitmap.CompressFormat.JPEG, 55, stream)) return null
                stream.toByteArray()
            }
        } finally {
            // These bitmaps are only encoding intermediates; the UI uses a Surface.
            if (scaled !== rotated && scaled !== decoded) scaled?.recycle()
            if (rotated !== decoded) rotated?.recycle()
            decoded.recycle()
        }
    }

    private fun fail(message: String) { stop(); onError(message) }

    fun stop() {
        closed = true
        // Camera callbacks and cleanup are serialized on their worker. An open
        // still in flight must receive onOpened so its device can be closed.
        val worker = handler
        if (worker != null) worker.post { releaseOnWorker() }
        else releaseOnWorker()
    }

    private fun releaseOnWorker() {
        runCatching { session?.close() }; session = null
        runCatching { camera?.close() }; camera = null
        runCatching { reader?.close() }; reader = null
        if (!opening) { thread?.quitSafely(); thread = null; handler = null }
    }
}
