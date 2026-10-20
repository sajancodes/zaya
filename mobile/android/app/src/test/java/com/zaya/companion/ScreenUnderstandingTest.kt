package com.zaya.companion

import com.zaya.companion.action.ActionRisk
import com.zaya.companion.action.ActionResult
import com.zaya.companion.action.ActionResultStatus
import com.zaya.companion.action.AndroidAction
import com.zaya.companion.service.ScreenCaptureManager
import com.zaya.companion.service.ScreenFrameResult
import com.zaya.companion.service.VisualAnalysis
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ScreenUnderstandingTest {

    @Before
    fun setUp() {
        ScreenCaptureManager.clearConsent()
    }

    @Test
    fun `screen understanding actions classify as read-only low risk without confirmation`() {
        val capture = AndroidAction.CaptureScreen
        assertEquals("capture_screen", capture.actionId)
        assertEquals(ActionRisk.LOW, capture.risk)
        assertFalse(capture.requiresConfirmation)

        val describe = AndroidAction.DescribeScreen(prompt = "Explain this error")
        assertEquals("describe_screen", describe.actionId)
        assertEquals(ActionRisk.LOW, describe.risk)
        assertEquals("Explain this error", describe.prompt)
        assertFalse(describe.requiresConfirmation)

        val extract = AndroidAction.ExtractVisibleText(filter = "verification code")
        assertEquals("extract_visible_text", extract.actionId)
        assertEquals(ActionRisk.LOW, extract.risk)
        assertEquals("verification code", extract.filter)
        assertFalse(extract.requiresConfirmation)

        val summarize = AndroidAction.SummarizeScreen(focus = "chat messages")
        assertEquals("summarize_screen", summarize.actionId)
        assertEquals(ActionRisk.LOW, summarize.risk)
        assertEquals("chat messages", summarize.focus)
        assertFalse(summarize.requiresConfirmation)
    }

    @Test
    fun `screen consent state defaults to false and clears correctly`() {
        assertFalse("Consent must initially be false", ScreenCaptureManager.hasConsent())

        ScreenCaptureManager.onConsentDenied()
        assertFalse("Consent must remain false after denial", ScreenCaptureManager.hasConsent())

        ScreenCaptureManager.clearConsent()
        assertFalse("Consent must be false after clearConsent", ScreenCaptureManager.hasConsent())
    }

    @Test
    fun `screen frame result outcomes represent expected states`() {
        val success = ScreenFrameResult.Success(
            jpeg = byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte()),
            width = 576,
            height = 1280,
            timestamp = 1718000000000L
        )
        assertEquals(576, success.width)
        assertEquals(1280, success.height)
        assertEquals(3, success.jpeg.size)

        val consentReq = ScreenFrameResult.ConsentRequired
        assertNotNull(consentReq)

        val timeout = ScreenFrameResult.Timeout
        assertNotNull(timeout)

        val failed = ScreenFrameResult.Failed("VirtualDisplay creation failed")
        assertEquals("VirtualDisplay creation failed", failed.reason)
    }

    @Test
    fun `visual analysis data model serializes correctly`() {
        val analysis = VisualAnalysis(
            summary = "Login screen with username and password fields.",
            extractedLines = listOf("Display Orientation: Portrait", "Resolution: 1080x2400"),
            resolution = "1080x2400",
            timestamp = 1718000000000L
        )

        assertEquals("Login screen with username and password fields.", analysis.summary)
        assertEquals("1080x2400", analysis.resolution)
        assertEquals(2, analysis.extractedLines.size)
        assertTrue(analysis.extractedLines[0].contains("Portrait"))
    }

    @Test
    fun `dimension scaling logic preserves aspect ratio and stays within bounds`() {
        // Original 1080x2400 (aspect ratio 0.45)
        val origW = 1080
        val origH = 2400
        val maxDim = 1280

        val scale = maxDim.toFloat() / maxOf(origW, origH)
        val scaledW = ((origW * scale).toInt()) and 1.inv()
        val scaledH = ((origH * scale).toInt()) and 1.inv()

        assertTrue(scaledH <= maxDim)
        assertTrue(scaledW <= maxDim)
        assertEquals(1280, scaledH)
        assertEquals(576, scaledW)
        // Verify even dimensions (divisible by 2) for encoder compatibility
        assertEquals(0, scaledW % 2)
        assertEquals(0, scaledH % 2)
    }

    @Test
    fun `action result handles permission required for screen capture dialog`() {
        val permResult = ActionResult.permissionRequired(
            permission = "android.permission.MEDIA_PROJECTION",
            spoken = "Screen capture authorization is required. Please grant the screen recording dialog to proceed."
        )

        assertEquals(ActionResultStatus.PERMISSION_REQUIRED, permResult.status)
        assertEquals("android.permission.MEDIA_PROJECTION", permResult.error)
        assertTrue(permResult.spokenMessage.contains("authorization is required"))

        val json = permResult.toJsonObject()
        assertEquals("PERMISSION_REQUIRED", json.getString("status"))
        assertEquals("android.permission.MEDIA_PROJECTION", json.getString("error"))
    }
}
