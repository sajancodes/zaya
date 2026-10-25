package com.zaya.companion.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Context
import android.content.Intent
import android.graphics.Path
import android.graphics.Rect
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.util.Locale
import kotlin.coroutines.coroutineContext
import kotlin.coroutines.resume

sealed class ScrollOutcome {
    data class Success(val direction: String, val count: Int) : ScrollOutcome()
    data class Cancelled(val completedCount: Int) : ScrollOutcome()
    data class Failed(val reason: String) : ScrollOutcome()
}

sealed class TapOutcome {
    data class Success(val target: String) : TapOutcome()
    data class RequiresConfirmation(val label: String, val reason: String) : TapOutcome()
    data class SecurityRestricted(val reason: String) : TapOutcome()
    data class NotFound(val label: String) : TapOutcome()
    data class Ambiguous(val label: String, val count: Int) : TapOutcome()
    data class Failed(val reason: String) : TapOutcome()
}

data class ScreenSnapshot(
    val packageName: String?,
    val windowTitle: String?,
    val visibleTexts: List<String>,
    val interactiveLabels: List<String>,
    val hasPasswordFields: Boolean,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * Narrowly scoped, policy-compliant AccessibilityService for user-directed scrolling,
 * semantic UI clicks, and system navigation.
 */
class ZayaInteractionService : AccessibilityService() {

    companion object {
        private const val TAG = "ZayaInteraction"
        const val MAX_SCROLL_REPETITIONS = 5
        const val MAX_INTERACTION_DURATION_MS = 15000L

        private val CONSEQUENTIAL_WORDS = setOf(
            "buy", "purchase", "pay", "payment", "delete", "remove",
            "clear", "wipe", "transfer", "submit", "confirm", "send",
            "order", "checkout", "subscribe"
        )

        @Volatile
        private var instance: ZayaInteractionService? = null

        fun isServiceEnabled(): Boolean = instance != null

        fun getInstance(): ZayaInteractionService? = instance

        fun openAccessibilitySettings(context: Context) {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
        }
    }

    private val mainHandler = Handler(Looper.getMainLooper())
    private var activeJob: Job? = null

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.i(TAG, "ZayaInteractionService connected and active.")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Only observe window state changes to verify active package readiness
    }

    override fun onInterrupt() {
        Log.w(TAG, "ZayaInteractionService interrupted by Android system.")
        stopActiveInteraction()
    }

    override fun onDestroy() {
        super.onDestroy()
        if (instance === this) {
            instance = null
        }
        stopActiveInteraction()
        Log.i(TAG, "ZayaInteractionService destroyed.")
    }

    fun stopActiveInteraction() {
        activeJob?.cancel(CancellationException("Interaction stopped by user request"))
        activeJob = null
    }

    /**
     * Executes user-directed scrolling across a given [direction] with bounded [count].
     */
    suspend fun scroll(
        direction: String,
        count: Int = 1,
        distance: String = "medium"
    ): ScrollOutcome = withContext(Dispatchers.Default) {
        val safeCount = count.coerceIn(1, MAX_SCROLL_REPETITIONS)
        val normalizedDir = direction.lowercase(Locale.ROOT).trim()

        if (normalizedDir !in setOf("down", "up", "left", "right")) {
            return@withContext ScrollOutcome.Failed("Invalid scroll direction: '$direction'. Must be up, down, left, or right.")
        }

        val metrics = resources.displayMetrics
        val width = metrics.widthPixels.toFloat()
        val height = metrics.heightPixels.toFloat()

        val distanceFraction = when (distance.lowercase(Locale.ROOT)) {
            "little" -> 0.25f
            "page" -> 0.70f
            else -> 0.45f // "medium"
        }

        var completed = 0
        try {
            for (i in 0 until safeCount) {
                coroutineContext.ensureActive()

                val (startX, startY, endX, endY) = when (normalizedDir) {
                    "down" -> {
                        val startYPos = height * 0.70f
                        val endYPos = (height * 0.70f) - (height * distanceFraction)
                        Quad(width * 0.5f, startYPos, width * 0.5f, endYPos.coerceAtLeast(height * 0.1f))
                    }
                    "up" -> {
                        val startYPos = height * 0.30f
                        val endYPos = (height * 0.30f) + (height * distanceFraction)
                        Quad(width * 0.5f, startYPos, width * 0.5f, endYPos.coerceAtMost(height * 0.9f))
                    }
                    "left" -> {
                        val startXPos = width * 0.75f
                        val endXPos = (width * 0.75f) - (width * distanceFraction)
                        Quad(startXPos, height * 0.5f, endXPos.coerceAtLeast(width * 0.1f), height * 0.5f)
                    }
                    "right" -> {
                        val startXPos = width * 0.25f
                        val endXPos = (width * 0.25f) + (width * distanceFraction)
                        Quad(startXPos, height * 0.5f, endXPos.coerceAtMost(width * 0.9f), height * 0.5f)
                    }
                    else -> Quad(0f, 0f, 0f, 0f)
                }

                val gestureSuccess = dispatchSwipe(startX, startY, endX, endY, durationMs = 300L)
                if (!gestureSuccess) {
                    return@withContext ScrollOutcome.Failed("Gesture dispatch failed on attempt ${i + 1}.")
                }

                completed++
                if (i < safeCount - 1) {
                    delay(700L) // Settle time between scrolls
                }
            }
            ScrollOutcome.Success(normalizedDir, completed)
        } catch (e: CancellationException) {
            ScrollOutcome.Cancelled(completed)
        } catch (e: Exception) {
            ScrollOutcome.Failed("Scrolling encountered error: ${e.message}")
        }
    }

    /**
     * Navigates reels / short-video content.
     */
    suspend fun navigateReel(action: String, count: Int = 1): ScrollOutcome {
        val normalized = action.lowercase(Locale.ROOT).trim()
        val dir = when (normalized) {
            "previous", "prev", "up" -> "up"
            else -> "down" // "next" reel is swiping up to reveal content below
        }
        return scroll(direction = dir, count = count, distance = "page")
    }

    /**
     * Taps a specific physical screen coordinate (x, y).
     */
    suspend fun tapCoordinates(x: Float, y: Float): Boolean {
        val metrics = resources.displayMetrics
        if (x < 0 || x > metrics.widthPixels || y < 0 || y > metrics.heightPixels) {
            Log.w(TAG, "Coordinates ($x, $y) are out of screen bounds (${metrics.widthPixels}x${metrics.heightPixels})")
            return false
        }
        return dispatchSwipe(startX = x, startY = y, endX = x, endY = y, durationMs = 50L)
    }

    /**
     * Finds and taps a visible UI element matching [label] semantically.
     */
    suspend fun tapByLabel(label: String, confirmed: Boolean = false): TapOutcome = withContext(Dispatchers.Default) {
        val cleanLabel = label.trim()
        if (cleanLabel.isBlank()) {
            return@withContext TapOutcome.Failed("Target label cannot be blank.")
        }

        // Consequential keyword protection
        val words = cleanLabel.lowercase(Locale.ROOT).split("\\s+".toRegex())
        val containsConsequential = words.any { it in CONSEQUENTIAL_WORDS }
        if (containsConsequential && !confirmed) {
            return@withContext TapOutcome.RequiresConfirmation(
                label = cleanLabel,
                reason = "Tapping '$cleanLabel' may submit data, place an order, or make permanent changes."
            )
        }

        val rootNode = rootInActiveWindow ?: return@withContext TapOutcome.Failed(
            "Screen content is not currently accessible or is protected by a secure window."
        )

        val matches = mutableListOf<AccessibilityNodeInfo>()
        findMatchingNodes(rootNode, cleanLabel.lowercase(Locale.ROOT), matches)

        if (matches.isEmpty()) {
            return@withContext TapOutcome.NotFound(cleanLabel)
        }

        if (matches.size > 3) {
            return@withContext TapOutcome.Ambiguous(cleanLabel, matches.size)
        }

        // Pick the first actionable interactive node
        val targetNode = matches.firstOrNull { it.isClickable || it.parent?.isClickable == true } ?: matches.first()

        // Security check: Never tap password fields
        if (targetNode.isPassword || targetNode.parent?.isPassword == true) {
            return@withContext TapOutcome.SecurityRestricted("Direct interaction with password or secure input fields is restricted.")
        }

        // Attempt accessibility click action first
        if (targetNode.isClickable && targetNode.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
            return@withContext TapOutcome.Success(cleanLabel)
        }

        val parent = targetNode.parent
        if (parent != null && parent.isClickable && parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
            return@withContext TapOutcome.Success(cleanLabel)
        }

        // Fallback: Dispatch physical tap at node's screen center
        val bounds = Rect()
        targetNode.getBoundsInScreen(bounds)
        if (bounds.width() > 0 && bounds.height() > 0) {
            val success = tapCoordinates(bounds.centerX().toFloat(), bounds.centerY().toFloat())
            return@withContext if (success) {
                TapOutcome.Success(cleanLabel)
            } else {
                TapOutcome.Failed("Physical tap at bounds center failed.")
            }
        }

        TapOutcome.Failed("Target element '$cleanLabel' was found but could not be clicked.")
    }

    private fun findMatchingNodes(
        node: AccessibilityNodeInfo,
        query: String,
        outList: MutableList<AccessibilityNodeInfo>
    ) {
        val text = node.text?.toString()?.lowercase(Locale.ROOT) ?: ""
        val desc = node.contentDescription?.toString()?.lowercase(Locale.ROOT) ?: ""

        if (text.contains(query) || desc.contains(query)) {
            outList.add(node)
        }

        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            findMatchingNodes(child, query, outList)
        }
    }

    /**
     * Extracts non-sensitive visible text and interactive labels from the active window hierarchy.
     * Password fields are strictly omitted to safeguard private credentials.
     */
    fun extractScreenSnapshot(): ScreenSnapshot {
        val rootNode = rootInActiveWindow ?: return ScreenSnapshot(
            packageName = null,
            windowTitle = null,
            visibleTexts = emptyList(),
            interactiveLabels = emptyList(),
            hasPasswordFields = false
        )

        val texts = mutableListOf<String>()
        val interactive = mutableListOf<String>()
        var foundPassword = false

        fun traverse(node: AccessibilityNodeInfo) {
            if (node.isPassword) {
                foundPassword = true
                return // Never inspect or collect password characters!
            }

            val text = node.text?.toString()?.trim()
            val desc = node.contentDescription?.toString()?.trim()

            if (!text.isNullOrBlank()) {
                texts.add(text)
            }
            if (!desc.isNullOrBlank() && desc != text) {
                texts.add(desc)
            }

            if (node.isClickable) {
                val label = text ?: desc
                if (!label.isNullOrBlank()) {
                    interactive.add(label)
                }
            }

            for (i in 0 until node.childCount) {
                val child = node.getChild(i) ?: continue
                traverse(child)
            }
        }

        traverse(rootNode)

        return ScreenSnapshot(
            packageName = rootNode.packageName?.toString(),
            windowTitle = rootNode.windowId.toString(),
            visibleTexts = texts,
            interactiveLabels = interactive,
            hasPasswordFields = foundPassword
        )
    }

    /**
     * Triggers Android system back navigation.
     */
    fun navigateBack(): Boolean = performGlobalAction(GLOBAL_ACTION_BACK)

    /**
     * Triggers Android system home navigation.
     */
    fun navigateHome(): Boolean = performGlobalAction(GLOBAL_ACTION_HOME)

    private suspend fun dispatchSwipe(
        startX: Float, startY: Float,
        endX: Float, endY: Float,
        durationMs: Long
    ): Boolean = suspendCancellableCoroutine { continuation ->
        val path = Path().apply {
            moveTo(startX, startY)
            lineTo(endX, endY)
        }

        val stroke = GestureDescription.StrokeDescription(path, 0L, durationMs.coerceAtLeast(1L))
        val gesture = GestureDescription.Builder().addStroke(stroke).build()

        val callback = object : GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                if (continuation.isActive) {
                    continuation.resume(true)
                }
            }

            override fun onCancelled(gestureDescription: GestureDescription?) {
                if (continuation.isActive) {
                    continuation.resume(false)
                }
            }
        }

        val dispatched = dispatchGesture(gesture, callback, mainHandler)
        if (!dispatched && continuation.isActive) {
            continuation.resume(false)
        }
    }

    private data class Quad(val x1: Float, val y1: Float, val x2: Float, val y2: Float)
}
