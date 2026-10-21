package com.zaya.companion.action

import android.Manifest
import android.content.ContentUris
import android.content.Context
import android.content.Intent
import android.os.Build
import android.provider.MediaStore
import androidx.core.net.toUri

/** On-demand media index only. No background library upload or unrestricted file access. */
class PhoneMedia(private val context: Context) {
    fun browse(action: AndroidAction.BrowseMedia): ActionResult {
        val collection = when (action.kind) {
            "photos" -> MediaStore.Images.Media.EXTERNAL_CONTENT_URI
            "videos" -> MediaStore.Video.Media.EXTERNAL_CONTENT_URI
            "audio" -> MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
            else -> return ActionResult.failure("Choose photos, videos or audio.")
        }
        val permission = if (Build.VERSION.SDK_INT < 33) Manifest.permission.READ_EXTERNAL_STORAGE else when (action.kind) {
            "photos" -> Manifest.permission.READ_MEDIA_IMAGES
            "videos" -> Manifest.permission.READ_MEDIA_VIDEO
            else -> Manifest.permission.READ_MEDIA_AUDIO
        }
        val registry = ActionRegistry(context)
        val selectedOnly = !registry.hasPermission(permission) && Build.VERSION.SDK_INT >= 34 && action.kind != "audio" &&
            registry.hasPermission(Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED)
        if (!registry.hasPermission(permission) && !selectedOnly)
            return ActionResult.permissionRequired(permission, "Allow access to your ${action.kind} on the phone.")
        return try {
            if (action.uri.isNotBlank()) {
                val uri = action.uri.toUri()
                if (uri.scheme != "content" || uri.authority != collection.authority || uri.pathSegments.dropLast(1) != collection.pathSegments ||
                    uri.lastPathSegment?.toLongOrNull() == null || uri.query != null || uri.fragment != null)
                    return ActionResult.failure("Choose a media URI returned by the phone media search.")
                context.startActivity(Intent(Intent.ACTION_VIEW, uri)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION))
                ActionResult.success("Opened the selected media on your phone.")
            } else {
                val items = mutableListOf<Map<String, Any?>>()
                val fields = arrayOf(MediaStore.MediaColumns._ID, MediaStore.MediaColumns.DISPLAY_NAME,
                    MediaStore.MediaColumns.MIME_TYPE, MediaStore.MediaColumns.SIZE)
                context.contentResolver.query(collection, fields,
                    "${MediaStore.MediaColumns.DISPLAY_NAME} LIKE ?", arrayOf("%${action.query.take(120)}%"),
                    "${MediaStore.MediaColumns.DATE_ADDED} DESC")?.use { rows ->
                    while (items.size < action.limit.coerceIn(1, 20) && rows.moveToNext()) {
                        items += mapOf("uri" to ContentUris.withAppendedId(collection, rows.getLong(0)).toString(),
                            "name" to rows.getString(1), "mime_type" to rows.getString(2), "size" to rows.getLong(3))
                    }
                }
                ActionResult.success("Found ${items.size} media items.", mapOf("items" to items, "selected_only" to selectedOnly))
            }
        } catch (_: SecurityException) { ActionResult.permissionRequired(permission) }
        catch (_: Exception) { ActionResult.failure("Could not access the selected phone media.") }
    }
}
