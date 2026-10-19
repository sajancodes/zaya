package com.zaya.companion.service

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import android.util.Log

/**
 * Android App Launcher and Deep Link Router.
 * Resolves natural language spoken app names to installed application packages
 * and dispatches native deep links for YouTube, Spotify, Maps, and Settings.
 */
class AppLauncher(private val context: Context) {

    private val packageManager: PackageManager = context.packageManager

    fun launchAppByName(name: String): Boolean {
        val target = name.trim().lowercase()
        if (target.isEmpty()) return false

        // Common shortcuts
        when (target) {
            "settings" -> return launchIntent(Intent(Settings.ACTION_SETTINGS))
            "youtube" -> return openDeepLink("youtube", "")
            "spotify" -> return openDeepLink("spotify", "")
            "maps" -> return openDeepLink("maps", "")
            "chrome", "browser" -> {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse("https://www.google.com"))
                if (launchIntent(intent)) return true
            }
        }

        // Match against installed apps
        val apps = packageManager.getInstalledApplications(PackageManager.GET_META_DATA)
        var bestMatch: ApplicationInfo? = null

        for (app in apps) {
            val label = packageManager.getApplicationLabel(app).toString().lowercase()
            if (label == target) {
                bestMatch = app
                break
            }
            if (label.contains(target) || app.packageName.lowercase().contains(target)) {
                if (bestMatch == null) bestMatch = app
            }
        }

        val pkg = bestMatch?.packageName ?: target
        val launchIntent = packageManager.getLaunchIntentForPackage(pkg) ?: run {
            Log.w("AppLauncher", "No launch intent found for $pkg")
            return false
        }
        return launchIntent(launchIntent)
    }

    fun openDeepLink(targetApp: String, query: String): Boolean {
        val app = targetApp.trim().lowercase()
        val q = query.trim()

        val intent = when (app) {
            "youtube" -> {
                if (q.isNotEmpty()) {
                    Intent(Intent.ACTION_VIEW, Uri.parse("vnd.youtube://results?search_query=${Uri.encode(q)}"))
                } else {
                    Intent(Intent.ACTION_VIEW, Uri.parse("vnd.youtube://"))
                }
            }
            "spotify" -> {
                if (q.isNotEmpty()) {
                    Intent(Intent.ACTION_VIEW, Uri.parse("spotify:search:${Uri.encode(q)}"))
                } else {
                    Intent(Intent.ACTION_VIEW, Uri.parse("spotify:"))
                }
            }
            "maps" -> {
                if (q.isNotEmpty()) {
                    Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=${Uri.encode(q)}"))
                } else {
                    Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0"))
                }
            }
            else -> {
                if (q.startsWith("http://") || q.startsWith("https://") || q.contains("://")) {
                    Intent(Intent.ACTION_VIEW, Uri.parse(q))
                } else {
                    packageManager.getLaunchIntentForPackage(app)
                }
            }
        } ?: return false

        return launchIntent(intent)
    }

    private fun launchIntent(intent: Intent): Boolean {
        return try {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            Log.e("AppLauncher", "Failed to launch intent: ${e.message}")
            false
        }
    }
}
