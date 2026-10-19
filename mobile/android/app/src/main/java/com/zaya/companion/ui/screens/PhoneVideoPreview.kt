package com.zaya.companion.ui.screens

import android.graphics.Matrix
import android.graphics.SurfaceTexture
import android.view.Surface
import android.view.TextureView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.zaya.companion.audio.PhoneCamera
import com.zaya.companion.runtime.ZayaRuntime

/** The local preview is rendered by Camera2, independently of model samples. */
@Composable
fun PhoneVideoPreview(runtime: ZayaRuntime, modifier: Modifier = Modifier) {
    val geometry by runtime.videoGeometry.collectAsStateWithLifecycle()
    val currentGeometry by rememberUpdatedState(geometry)
    AndroidView(modifier = modifier, factory = { context ->
        TextureView(context).apply {
            surfaceTextureListener = object : TextureView.SurfaceTextureListener {
                private var surface: Surface? = null
                override fun onSurfaceTextureAvailable(texture: SurfaceTexture, width: Int, height: Int) {
                    val created = Surface(texture)
                    surface = created
                    runtime.attachVideoPreview(created) { bufferWidth, bufferHeight ->
                        texture.setDefaultBufferSize(bufferWidth, bufferHeight)
                    }
                }
                override fun onSurfaceTextureSizeChanged(texture: SurfaceTexture, width: Int, height: Int) {
                    updateGeometry(this@apply, currentGeometry)
                }
                override fun onSurfaceTextureDestroyed(texture: SurfaceTexture): Boolean {
                    surface?.let { runtime.detachVideoPreview(it); it.release() }
                    surface = null
                    return true
                }
                override fun onSurfaceTextureUpdated(texture: SurfaceTexture) = Unit
            }
        }
    }, update = { texture -> updateGeometry(texture, geometry) })
}

private fun updateGeometry(view: TextureView, geometry: PhoneCamera.Geometry?) {
    if (geometry == null || view.width == 0 || view.height == 0) return
    val rotated = geometry.rotation % 180 != 0
    val rotatedWidth = if (rotated) geometry.height else geometry.width
    val rotatedHeight = if (rotated) geometry.width else geometry.height
    val scale = maxOf(view.width.toFloat() / rotatedWidth, view.height.toFloat() / rotatedHeight)
    val transform = Matrix().apply {
        setScale(geometry.width.toFloat() / view.width, geometry.height.toFloat() / view.height)
        postTranslate(-geometry.width / 2f, -geometry.height / 2f)
        postRotate(geometry.rotation.toFloat())
        postScale(scale, scale)
        postTranslate(view.width / 2f, view.height / 2f)
        if (geometry.front) postScale(-1f, 1f, view.width / 2f, view.height / 2f)
    }
    view.setTransform(transform)
}
