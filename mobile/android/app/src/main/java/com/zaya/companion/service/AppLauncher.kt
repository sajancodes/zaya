package com.zaya.companion.service

import android.content.Context
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import android.util.Log

sealed class AppLaunchOutcome {
    data class Success(val appName: String, val packageName: String) : AppLaunchOutcome()
    data class Ambiguous(val query: String, val candidates: List<String>) : AppLaunchOutcome()
    data class NotFound(val query: String) : AppLaunchOutcome()
    data class Disabled(val appName: String, val packageName: String) : AppLaunchOutcome()
    data class Failed(val appName: String, val reason: String) : AppLaunchOutcome()
}

/**
 * Android App Launcher and Deep Link Router.
 * Resolves natural language spoken app names to installed application packages
 * and dispatches native deep links for YouTube, Spotify, Maps, and Settings.
 */
class AppLauncher(private val context: Context) {

    private val packageManager: PackageManager = context.packageManager

    fun resolveAndLaunch(name: String): AppLaunchOutcome {
        val target = name.trim().lowercase()
        if (target.isEmpty()) return AppLaunchOutcome.NotFound(name)

        // Common hardcoded direct shortcuts
        when (target) {
            "settings" -> {
                val ok = launchIntent(Intent(Settings.ACTION_SETTINGS))
                return if (ok) AppLaunchOutcome.Success("Settings", "com.android.settings")
                else AppLaunchOutcome.Failed("Settings", "Failed to launch Settings intent.")
            }
            "youtube" -> {
                val ok = openDeepLink("youtube", "")
                return if (ok) AppLaunchOutcome.Success("YouTube", "com.google.android.youtube")
                else AppLaunchOutcome.Failed("YouTube", "YouTube is not installed.")
            }
            "spotify" -> {
                val ok = openDeepLink("spotify", "")
                return if (ok) AppLaunchOutcome.Success("Spotify", "com.spotify.music")
                else AppLaunchOutcome.Failed("Spotify", "Spotify is not installed.")
            }
            "maps" -> {
                val ok = openDeepLink("maps", "")
                return if (ok) AppLaunchOutcome.Success("Google Maps", "com.google.android.apps.maps")
                else AppLaunchOutcome.Failed("Google Maps", "Maps app is not installed.")
            }
            "whatsapp" -> {
                val ok = openDeepLink("whatsapp", "")
                return if (ok) AppLaunchOutcome.Success("WhatsApp", "com.whatsapp")
                else AppLaunchOutcome.Failed("WhatsApp", "WhatsApp is not installed.")
            }
            "calendar" -> {
                val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_APP_CALENDAR)
                val ok = launchIntent(intent)
                return if (ok) AppLaunchOutcome.Success("Calendar", "calendar")
                else AppLaunchOutcome.NotFound("Calendar")
            }
        }

        // Query installed applications
        val apps = packageManager.getInstalledApplications(PackageManager.GET_META_DATA)
        val exactMatches = mutableListOf<ApplicationInfo>()
        val fuzzyMatches = mutableListOf<ApplicationInfo>()

        for (app in apps) {
            val label = packageManager.getApplicationLabel(app).toString().lowercase()
            val pkg = app.packageName.lowercase()

            if (label == target || pkg == target) {
                exactMatches.add(app)
            } else if (label.contains(target) || pkg.contains(target)) {
                fuzzyMatches.add(app)
            }
        }

        val candidates = if (exactMatches.isNotEmpty()) exactMatches else fuzzyMatches

        if (candidates.isEmpty()) {
            return AppLaunchOutcome.NotFound(name)
        }

        if (candidates.size > 1 && exactMatches.isEmpty()) {
            val candidateNames = candidates.map { packageManager.getApplicationLabel(it).toString() }.distinct()
            if (candidateNames.size > 1) {
                return AppLaunchOutcome.Ambiguous(name, candidateNames.take(4))
            }
        }

        val chosen = candidates.first()
        val appLabel = packageManager.getApplicationLabel(chosen).toString()

        if (!chosen.enabled) {
            return AppLaunchOutcome.Disabled(appLabel, chosen.packageName)
        }

        val launchIntent = packageManager.getLaunchIntentForPackage(chosen.packageName)
            ?: return AppLaunchOutcome.Failed(appLabel, "App does not declare a main launcher activity.")

        val launched = launchIntent(launchIntent)
        return if (launched) {
            AppLaunchOutcome.Success(appLabel, chosen.packageName)
        } else {
            AppLaunchOutcome.Failed(appLabel, "System refused to start activity.")
        }
    }

    fun launchAppByName(name: String): Boolean {
        return resolveAndLaunch(name) is AppLaunchOutcome.Success
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
            "whatsapp" -> {
                packageManager.getLaunchIntentForPackage("com.whatsapp")
                    ?: Intent(Intent.ACTION_VIEW, Uri.parse("https://api.whatsapp.com"))
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
