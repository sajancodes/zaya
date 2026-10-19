package com.zaya.companion.net

import android.content.ContentResolver
import android.net.Uri
import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody
import okio.BufferedSink
import okio.source
import java.io.IOException

/**
 * Streams a picked file straight off the content resolver into the upload.
 *
 * `asRequestBody()` would need a real file on disk, which means copying the
 * owner's video into the app's cache first. This reads it once, from wherever
 * the picker put it.
 */
class ContentUriBody(
    private val resolver: ContentResolver,
    private val uri: Uri,
    private val name: String,
) : RequestBody() {
    override fun contentType(): MediaType = OCTET_STREAM

    override fun contentLength(): Long = runCatching {
        resolver.openAssetFileDescriptor(uri, "r")?.use { descriptor -> descriptor.length }
            ?: -1L
    }.getOrDefault(-1L)

    override fun writeTo(sink: BufferedSink) {
        val stream = try {
            resolver.openInputStream(uri)
        } catch (error: Exception) {
            throw IOException("Cannot read $name", error)
        } ?: throw IOException("Cannot read $name")
        stream.use { input -> sink.writeAll(input.source()) }
    }

    private companion object {
        val OCTET_STREAM = "application/octet-stream".toMediaType()
    }
}
