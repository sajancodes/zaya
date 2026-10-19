package com.zaya.companion.ui

import android.content.Context
import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import com.zaya.companion.protocol.Protocol

/**
 * Zaya's face on this phone.
 *
 * The images are the owner's: anything dropped into `mobile/android/assets/` as
 * `zaya_<name>.png` wins, and the crop of the existing desktop art bundled in
 * `res/drawable-nodpi` is the fallback. Nothing is drawn here — the phone shows
 * the picture the laptop's state asks for, and if that picture does not exist it
 * shows Zaya's neutral face rather than a blank screen.
 */
object ZayaArt {
    private val cache = LruCache<String, ImageBitmap>(6)

    /** Candidate file names for a laptop state, best first. */
    fun candidates(state: String, emotion: String): List<String> = buildList {
        if (emotion.isNotBlank() && emotion != "neutral") add("zaya_$emotion")
        when (state) {
            Protocol.THINKING, Protocol.TASK_RUNNING -> add("zaya_thinking")
            Protocol.STANDBY, Protocol.SLEEPING, Protocol.CONNECTING -> add("zaya_standby")
        }
        add("zaya_neutral")
    }

    /** Blocking load; call from a background dispatcher. */
    fun load(context: Context, name: String): ImageBitmap? {
        cache.get(name)?.let { return it }
        val bitmap = fromAssets(context, name) ?: fromDrawables(context, name) ?: return null
        val image = bitmap.asImageBitmap()
        cache.put(name, image)
        return image
    }

    fun resolve(context: Context, state: String, emotion: String): ImageBitmap? {
        for (name in candidates(state, emotion)) {
            load(context, name)?.let { return it }
        }
        return null
    }

    private fun fromAssets(context: Context, name: String): android.graphics.Bitmap? = try {
        context.assets.open("$name.png").use { stream ->
            BitmapFactory.decodeStream(stream)
        }
    } catch (_: Exception) {
        null
    }

    private fun fromDrawables(context: Context, name: String): android.graphics.Bitmap? = try {
        val id = context.resources.getIdentifier(name, "drawable", context.packageName)
        if (id == 0) null else BitmapFactory.decodeResource(context.resources, id)
    } catch (_: Exception) {
        null
    }
}
