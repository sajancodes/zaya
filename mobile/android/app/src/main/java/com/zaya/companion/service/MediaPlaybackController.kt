package com.zaya.companion.service

import android.content.ComponentName
import android.content.Context
import android.media.AudioManager
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.util.Log
import android.view.KeyEvent

data class ActiveMediaStatus(
    val hasActiveSession: Boolean,
    val packageName: String? = null,
    val isPlaying: Boolean = false,
    val title: String? = null,
    val artist: String? = null,
    val album: String? = null,
    val requiresNotificationAccess: Boolean = false,
)

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

    fun hasNotificationAccess(): Boolean {
        val flat = android.provider.Settings.Secure.getString(
            context.contentResolver,
            "enabled_notification_listeners"
        ) ?: return false
        return flat.contains(context.packageName)
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

    fun getActiveMediaStatus(): ActiveMediaStatus {
        if (!hasNotificationAccess()) {
            return ActiveMediaStatus(hasActiveSession = false, requiresNotificationAccess = true)
        }
        val controllers = getActiveControllers()
        val active = controllers.firstOrNull() ?: return ActiveMediaStatus(hasActiveSession = false)

        val pbState = active.playbackState?.state
        val isPlaying = pbState == PlaybackState.STATE_PLAYING || pbState == PlaybackState.STATE_BUFFERING
        val metadata = active.metadata

        val title = metadata?.getString(MediaMetadata.METADATA_KEY_TITLE)
        val artist = metadata?.getString(MediaMetadata.METADATA_KEY_ARTIST)
        val album = metadata?.getString(MediaMetadata.METADATA_KEY_ALBUM)

        return ActiveMediaStatus(
            hasActiveSession = true,
            packageName = active.packageName,
            isPlaying = isPlaying,
            title = title,
            artist = artist,
            album = album,
        )
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

    fun stop(): Boolean {
        val controllers = getActiveControllers()
        if (controllers.isNotEmpty()) {
            controllers.first().transportControls.stop()
            return true
        }
        return dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_STOP)
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
            "stop" -> stop()
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
