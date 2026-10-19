package com.zaya.companion.service

import android.content.ComponentName
import android.content.Context
import android.media.AudioManager
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.util.Log
import android.view.KeyEvent

/**
 * System-wide media playback controller for Spotify, YouTube, Apple Music, and podcast players.
 *
 * Interacts with active [MediaController] sessions via [MediaSessionManager] when notification
 * listener access is granted, and falls back to system [AudioManager] media key events.
 */
class MediaPlaybackController(private val context: Context) {

    private val audioManager by lazy {
        context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
    }

    private val mediaSessionManager by lazy {
        context.getSystemService(Context.MEDIA_SESSION_SERVICE) as? MediaSessionManager
    }

    private fun getActiveControllers(): List<MediaController> {
        val manager = mediaSessionManager ?: return emptyList()
        return try {
            val component = ComponentName(context, ZayaNotificationListener::class.java)
            manager.getActiveSessions(component)
        } catch (e: SecurityException) {
            Log.w("MediaPlaybackController", "Notification access required for MediaSessionManager: ${e.message}")
            emptyList()
        } catch (e: Exception) {
            Log.e("MediaPlaybackController", "Failed to retrieve active media sessions: ${e.message}")
            emptyList()
        }
    }

    fun play(): Boolean {
        val controllers = getActiveControllers()
        if (controllers.isNotEmpty()) {
            controllers.first().transportControls.play()
            return true
        }
        return dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PLAY)
    }

    fun pause(): Boolean {
        val controllers = getActiveControllers()
        if (controllers.isNotEmpty()) {
            controllers.first().transportControls.pause()
            return true
        }
        return dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PAUSE)
    }

    fun toggle(): Boolean {
        val controllers = getActiveControllers()
        if (controllers.isNotEmpty()) {
            val controller = controllers.first()
            val state = controller.playbackState?.state
            if (state == PlaybackState.STATE_PLAYING) {
                controller.transportControls.pause()
            } else {
                controller.transportControls.play()
            }
            return true
        }
        return dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE)
    }

    fun next(): Boolean {
        val controllers = getActiveControllers()
        if (controllers.isNotEmpty()) {
            controllers.first().transportControls.skipToNext()
            return true
        }
        return dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_NEXT)
    }

    fun previous(): Boolean {
        val controllers = getActiveControllers()
        if (controllers.isNotEmpty()) {
            controllers.first().transportControls.skipToPrevious()
            return true
        }
        return dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PREVIOUS)
    }

    fun executeAction(action: String): Boolean {
        return when (action.lowercase().trim()) {
            "play" -> play()
            "pause" -> pause()
            "toggle" -> toggle()
            "next", "skip" -> next()
            "previous", "prev" -> previous()
            else -> false
        }
    }

    private fun dispatchMediaKey(keyCode: Int): Boolean {
        val am = audioManager ?: return false
        return try {
            val down = KeyEvent(KeyEvent.ACTION_DOWN, keyCode)
            val up = KeyEvent(KeyEvent.ACTION_UP, keyCode)
            am.dispatchMediaKeyEvent(down)
            am.dispatchMediaKeyEvent(up)
            true
        } catch (e: Exception) {
            Log.e("MediaPlaybackController", "Failed to dispatch media key $keyCode: ${e.message}")
            false
        }
    }
}
