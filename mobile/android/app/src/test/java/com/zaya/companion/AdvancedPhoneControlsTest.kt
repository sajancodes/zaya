package com.zaya.companion

import com.zaya.companion.action.ActionRisk
import com.zaya.companion.action.ActionResult
import com.zaya.companion.action.ActionResultStatus
import com.zaya.companion.action.AndroidAction
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AdvancedPhoneControlsTest {

    @Test
    fun `get flashlight state action has low risk and correct action id`() {
        val action = AndroidAction.GetFlashlightState
        assertEquals("get_flashlight_state", action.actionId)
        assertEquals(ActionRisk.LOW, action.risk)
        assertFalse(action.requiresConfirmation)
    }

    @Test
    fun `get media status action has low risk and correct action id`() {
        val action = AndroidAction.GetMediaStatus
        assertEquals("get_media_status", action.actionId)
        assertEquals(ActionRisk.LOW, action.risk)
        assertFalse(action.requiresConfirmation)
    }

    @Test
    fun `open system settings preserves panel and optional package name`() {
        val displayAction = AndroidAction.OpenSystemSettings("display")
        assertEquals("open_system_settings", displayAction.actionId)
        assertEquals("display", displayAction.settingType)
        assertEquals(null, displayAction.packageName)
        assertEquals(ActionRisk.LOW, displayAction.risk)
        assertFalse(displayAction.requiresConfirmation)

        val appDetailsAction = AndroidAction.OpenSystemSettings("app_details", "com.whatsapp")
        assertEquals("app_details", appDetailsAction.settingType)
        assertEquals("com.whatsapp", appDetailsAction.packageName)
    }

    @Test
    fun `flashlight state result serializes accurate status and data`() {
        val resultOn = ActionResult.success(
            spokenMessage = "The flashlight is on.",
            data = mapOf("is_on" to true, "available" to true)
        )
        val json = resultOn.toJsonObject()
        assertEquals("SUCCESS", json.getString("status"))
        assertEquals("The flashlight is on.", json.getString("spoken_message"))
        assertTrue(json.getJSONObject("data").getBoolean("is_on"))
        assertTrue(json.getJSONObject("data").getBoolean("available"))

        val resultNoFlash = ActionResult.failure(
            message = "This device does not have a camera flash.",
            error = "NO_FLASH_UNIT"
        )
        val jsonNoFlash = resultNoFlash.toJsonObject()
        assertEquals("FAILED", jsonNoFlash.getString("status"))
        assertEquals("NO_FLASH_UNIT", jsonNoFlash.getString("error"))
    }

    @Test
    fun `media status result reports active track or idle state`() {
        val activeResult = ActionResult.success(
            spokenMessage = "Now playing Believer by Imagine Dragons on Spotify.",
            data = mapOf(
                "is_playing" to true,
                "title" to "Believer",
                "artist" to "Imagine Dragons",
                "package_name" to "com.spotify.music"
            )
        )
        val json = activeResult.toJsonObject()
        assertEquals("SUCCESS", json.getString("status"))
        val data = json.getJSONObject("data")
        assertTrue(data.getBoolean("is_playing"))
        assertEquals("Believer", data.getString("title"))
        assertEquals("Imagine Dragons", data.getString("artist"))

        val noAccessResult = ActionResult.permissionRequired(
            permission = "android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS"
        )
        val jsonNoAccess = noAccessResult.toJsonObject()
        assertEquals("PERMISSION_REQUIRED", jsonNoAccess.getString("status"))
    }

    @Test
    fun `app launch outcome results format ambiguous and missing states`() {
        val ambiguousResult = ActionResult.failure(
            message = "I found multiple matching apps: YouTube, YouTube Music. Which one would you like to open?",
            error = "AMBIGUOUS_APP_NAME"
        )
        val jsonAmbiguous = ambiguousResult.toJsonObject()
        assertEquals("FAILED", jsonAmbiguous.getString("status"))
        assertEquals("AMBIGUOUS_APP_NAME", jsonAmbiguous.getString("error"))
        assertTrue(jsonAmbiguous.getString("spoken_message").contains("YouTube Music"))

        val notFoundResult = ActionResult.failure(
            message = "App 'Flappy Bird' is not installed on this device.",
            error = "APP_NOT_INSTALLED"
        )
        val jsonNotFound = notFoundResult.toJsonObject()
        assertEquals("APP_NOT_INSTALLED", jsonNotFound.getString("error"))
    }

    @Test
    fun `media controls support playback manipulation verbs`() {
        val verbs = listOf("play", "pause", "play_pause", "next", "previous", "stop")
        for (verb in verbs) {
            val action = AndroidAction.ControlMedia(verb)
            assertEquals("control_media", action.actionId)
            assertEquals(verb, action.command)
            assertEquals(ActionRisk.MEDIUM, action.risk)
        }
    }
}
