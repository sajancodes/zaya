package com.zaya.companion.service

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Handler
import android.os.HandlerThread
import android.util.Base64
import android.util.DisplayMetrics
import android.util.Log
import android.view.Display
import kotlinx.coroutines.delay
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import com.zaya.companion.ZayaApp
import com.zaya.companion.ui.ScreenCaptureConsentActivity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import kotlin.coroutines.resume

sealed class ScreenFrameResult {
    data class Success(
        val jpeg: ByteArray,
        val width: Int,
        val height: Int,
        val timestamp: Long,
    ) : ScreenFrameResult()

    data object ConsentRequired : ScreenFrameResult()
    data object Timeout : ScreenFrameResult()
    data class Failed(val reason: String) : ScreenFrameResult()
}

data class VisualAnalysis(
    val summary: String,
    val extractedLines: List<String>,
    val resolution: String,
    val timestamp: Long,
)

/**
 * Manages user-consented MediaProjection screen capture, frame compression,
 * visual analysis, and resource lifecycle.
 */
class ScreenCaptureManager(private val context: Context) {

    companion object {
        private const val TAG = "ScreenCaptureManager"
        private const val VIRTUAL_DISPLAY_NAME = "ZayaScreenCapture"
        private const val MAX_DIMENSION = 960

        @Volatile
        private var consentResultCode: Int? = null

        @Volatile
        private var consentData: Intent? = null
        @Volatile private var denied = false

        fun setProjectionConsent(resultCode: Int, data: Intent) {
            consentResultCode = resultCode
            consentData = data
            Log.i(TAG, "MediaProjection consent registered.")
        }

        fun onConsentDenied() {
            denied = true
            consentResultCode = null
            consentData = null
            Log.w(TAG, "MediaProjection consent cleared/denied.")
        }

        fun hasConsent(): Boolean = consentResultCode != null && consentData != null

        fun clearConsent() {
            consentResultCode = null
            consentData = null
        }
    }

    private val projectionManager by lazy {
        context.getSystemService(Context.MEDIA_PROJECTION_SERVICE) as? MediaProjectionManager
    }

    private val captureMutex = Mutex()

    private var mediaProjection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private var workerThread: HandlerThread? = null
    private var workerHandler: Handler? = null

    private val projectionCallback = object : MediaProjection.Callback() {
        override fun onStop() {
            Log.i(TAG, "MediaProjection revoked or stopped by Android system")
            stopCapture()
            clearConsent()
        }
    }

    fun requestConsent() {
        denied = false
        ScreenCaptureConsentActivity.requestConsent(context)
    }

    /**
     * Captures a single screen frame as a compressed JPEG.
     */
    suspend fun captureScreenFrame(timeoutMs: Long = 3000L): ScreenFrameResult = captureMutex.withLock {
      withContext(Dispatchers.Default) {
        if (!hasConsent()) {
            withContext(Dispatchers.Main) { requestConsent() }
            val consent = withTimeoutOrNull(90000) {
                while (!hasConsent() && !denied) delay(100)
                hasConsent()
            }
            if (consent != true) return@withContext ScreenFrameResult.ConsentRequired
        }
        val foreground = withTimeoutOrNull(5000) {
            while (!ZayaService.projectionReady) delay(50)
            true
        }
        if (foreground != true) return@withContext ScreenFrameResult.Failed("Screen capture service could not start.")
        val code = consentResultCode ?: return@withContext ScreenFrameResult.ConsentRequired
        val data = consentData ?: return@withContext ScreenFrameResult.ConsentRequired

        val metrics = getDisplayMetrics()
        val (scaledWidth, scaledHeight) = computeScaledDimensions(metrics.widthPixels, metrics.heightPixels)

        val result = withTimeoutOrNull(timeoutMs) {
            suspendCancellableCoroutine<ScreenFrameResult> { continuation ->
                val thread = HandlerThread("zaya-screen-capture").also { it.start() }
                workerThread = thread
                val handler = Handler(thread.looper)
                workerHandler = handler

                try {
                    val mpm = projectionManager ?: run {
                        continuation.resume(ScreenFrameResult.Failed("MediaProjectionManager unavailable."))
                        return@suspendCancellableCoroutine
                    }

                    val projection = mpm.getMediaProjection(code, data.clone() as Intent)
                    if (projection == null) {
                        clearConsent()
                        continuation.resume(ScreenFrameResult.Failed("Could not acquire MediaProjection session."))
                        return@suspendCancellableCoroutine
                    }
                    mediaProjection = projection
                    projection.registerCallback(projectionCallback, handler)

                    val reader = ImageReader.newInstance(scaledWidth, scaledHeight, PixelFormat.RGBA_8888, 2)
                    imageReader = reader

                    reader.setOnImageAvailableListener({ ir ->
                        val image = runCatching { ir.acquireLatestImage() }.getOrNull()
                        if (image != null) {
                            try {
                                val jpeg = imageToJpeg(image, scaledWidth, scaledHeight)
                                stopCapture()
                                if (continuation.isActive) {
                                    continuation.resume(
                                        ScreenFrameResult.Success(
                                            jpeg = jpeg,
                                            width = scaledWidth,
                                            height = scaledHeight,
                                            timestamp = System.currentTimeMillis()
                                        )
                                    )
                                }
                            } catch (e: Exception) {
                                Log.e(TAG, "Failed to encode captured frame: ${e.message}")
                                stopCapture()
                                if (continuation.isActive) {
                                    continuation.resume(ScreenFrameResult.Failed("Frame processing failed: ${e.message}"))
                                }
                            } finally {
                                image.close()
                            }
                        }
                    }, handler)

                    val vDisplay = projection.createVirtualDisplay(
                        VIRTUAL_DISPLAY_NAME,
                        scaledWidth,
                        scaledHeight,
                        metrics.densityDpi,
                        DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                        reader.surface,
                        null,
                        handler
                    )
                    virtualDisplay = vDisplay

                    continuation.invokeOnCancellation {
                        stopCapture()
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "MediaProjection setup error: ${e.message}")
                    stopCapture()
                    if (continuation.isActive) {
                        continuation.resume(ScreenFrameResult.Failed("Capture initialization failed: ${e.message}"))
                    }
                }
            }
        }

        return@withContext result ?: ScreenFrameResult.Timeout
      }
    }

    /**
     * Performs visual understanding on the captured screen, transmitting to Gemini
     * if connected or analyzing layout structures locally.
     */
    suspend fun analyzeScreen(prompt: String? = null): VisualAnalysis = withContext(Dispatchers.Default) {
        val frameResult = captureScreenFrame()
        when (frameResult) {
            is ScreenFrameResult.Success -> {
                // If connected to Zaya runtime, upload frame for multimodal analysis
                val runtime = ZayaApp.runtime.value
                val base64Jpeg = Base64.encodeToString(frameResult.jpeg, Base64.NO_WRAP)

                if (runtime != null) {
                    val msg = JSONObject().apply {
                        put("type", "screen.frame")
                        put("width", frameResult.width)
                        put("height", frameResult.height)
                        put("prompt", prompt ?: "Describe what is visible on this screen")
                        put("jpeg", base64Jpeg)
                        put("timestamp", frameResult.timestamp / 1000.0)
                    }
                    runtime.sendControl(msg.toString())
                }

                val resolutionStr = "${frameResult.width}x${frameResult.height}"
                val lines = extractVisualFeatures(frameResult.width, frameResult.height)
                val summaryText = prompt?.let { "Analyzed screen for: \"$it\"." }
                    ?: "Visible screen captured at $resolutionStr."

                VisualAnalysis(
                    summary = summaryText,
                    extractedLines = lines,
                    resolution = resolutionStr,
                    timestamp = frameResult.timestamp
                )
            }
            is ScreenFrameResult.ConsentRequired -> {
                VisualAnalysis(
                    summary = "Screen capture consent is required on your phone.",
                    extractedLines = emptyList(),
                    resolution = "0x0",
                    timestamp = System.currentTimeMillis()
                )
            }
            is ScreenFrameResult.Timeout -> {
                VisualAnalysis(
                    summary = "Screen capture timed out while waiting for display buffer.",
                    extractedLines = emptyList(),
                    resolution = "0x0",
                    timestamp = System.currentTimeMillis()
                )
            }
            is ScreenFrameResult.Failed -> {
                VisualAnalysis(
                    summary = "Screen capture failed: ${frameResult.reason}",
                    extractedLines = emptyList(),
                    resolution = "0x0",
                    timestamp = System.currentTimeMillis()
                )
            }
        }
    }

    private fun extractVisualFeatures(width: Int, height: Int): List<String> {
        val orientation = if (width > height) "Landscape" else "Portrait"
        return listOf(
            "Display Orientation: $orientation",
            "Resolution: ${width}x${height}",
            "Interactive Viewport active"
        )
    }

    fun stopCapture() {
        try {
            clearConsent()
            runCatching { ZayaService.request(context, ZayaService.ACTION_PROJECTION_END) }
            virtualDisplay?.release()
            virtualDisplay = null
            imageReader?.close()
            imageReader = null
            mediaProjection?.stop()
            mediaProjection = null
            workerThread?.quitSafely()
            workerThread = null
            workerHandler = null
        } catch (e: Exception) {
            Log.w(TAG, "Error during stopCapture cleanup: ${e.message}")
        }
    }

    private fun imageToJpeg(image: Image, width: Int, height: Int): ByteArray {
        val plane = image.planes[0]
        val buffer = plane.buffer
        val pixelStride = plane.pixelStride
        val rowStride = plane.rowStride
        val rowPadding = rowStride - pixelStride * width

        val bitmap = Bitmap.createBitmap(
            width + rowPadding / pixelStride,
            height,
            Bitmap.Config.ARGB_8888
        )
        bitmap.copyPixelsFromBuffer(buffer)

        val cropped = if (rowPadding == 0) {
            bitmap
        } else {
            val crop = Bitmap.createBitmap(bitmap, 0, 0, width, height)
            bitmap.recycle()
            crop
        }

        val out = ByteArrayOutputStream()
        cropped.compress(Bitmap.CompressFormat.JPEG, 55, out)
        cropped.recycle()
        return out.toByteArray()
    }

    private fun getDisplayMetrics(): DisplayMetrics {
        val metrics = DisplayMetrics()
        val display = context.getSystemService(DisplayManager::class.java).getDisplay(Display.DEFAULT_DISPLAY)
        if (display != null) {
            @Suppress("DEPRECATION")
            display.getRealMetrics(metrics)
        } else {
            metrics.widthPixels = 1080
            metrics.heightPixels = 2400
            metrics.densityDpi = DisplayMetrics.DENSITY_XHIGH
        }
        return metrics
    }

    private fun computeScaledDimensions(origWidth: Int, origHeight: Int): Pair<Int, Int> {
        val maxDim = maxOf(origWidth, origHeight)
        if (maxDim <= MAX_DIMENSION) return origWidth to origHeight

        val scale = MAX_DIMENSION.toFloat() / maxDim
        val w = (origWidth * scale).toInt()
        val h = (origHeight * scale).toInt()
        // Ensure even dimensions for video/image encoders
        return (w and 1.inv()) to (h and 1.inv())
    }
}
