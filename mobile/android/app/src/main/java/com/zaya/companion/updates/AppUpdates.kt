package com.zaya.companion.updates

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.provider.Settings
import android.net.Uri
import androidx.core.content.FileProvider
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.withContext
import java.io.File

data class UpdateState(
    val available: UpdateManifest? = null,
    val checking: Boolean = false,
    val downloading: Boolean = false,
    val percent: Int = 0,
    val ready: File? = null,
    val message: String = "",
)

/** Updates never install silently and never carry a GitHub credential on the phone. */
class AppUpdates(private val context: Context) {
    private val client = OkHttpClient.Builder().connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS).build()
    private val repository = "sajancodes/zaya-companion-releases"
    private var apkUrl = ""

    private suspend fun latest(): UpdateManifest? = withContext(Dispatchers.IO) {
        val request = Request.Builder().url("https://api.github.com/repos/$repository/releases/latest")
            .header("Accept", "application/vnd.github+json").header("User-Agent", "Zaya-Companion").build()
        val release = client.newCall(request).execute().use { response ->
            if (response.code == 404) return@withContext null
            check(response.isSuccessful) { "Update check unavailable" }
            JSONObject(response.body?.string() ?: "{}")
        }
        val tag = release.getString("tag_name")
        require(tag.matches(Regex("android-[0-9A-Za-z._-]{1,80}"))) { "Invalid release tag" }
        val base = "https://github.com/$repository/releases/download/$tag/"
        val manifestRequest = Request.Builder().url(base + "update.json").build()
        val manifest = client.newCall(manifestRequest).execute().use { response ->
            check(response.isSuccessful) { "Update manifest unavailable" }
            val body = response.body ?: error("Missing update manifest")
            val bytes = body.byteStream().use { input ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(4096)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    require(output.size() + count <= 16384) { "Invalid update manifest" }
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
            UpdateManifest.from(JSONObject(bytes.toString(Charsets.UTF_8)))
        }
        apkUrl = base + "Zaya-Companion.apk"
        manifest
    }

    private val mutable = MutableStateFlow(UpdateState())
    val state = mutable.asStateFlow()
    private val mutex = Mutex()
    private var lastCheck = 0L

    suspend fun check(force: Boolean = false) {
        if (!force && System.currentTimeMillis() - lastCheck < 6 * 60 * 60 * 1000L) return
        if (!mutex.tryLock()) return
        try {
            mutable.value = mutable.value.copy(checking = true, message = "")
            val manifest = latest()
            lastCheck = System.currentTimeMillis()
            val newer = manifest?.takeIf { it.code > installedVersion() }
            mutable.value = UpdateState(available = newer,
                message = if (newer == null) "You're up to date" else "Version ${newer.name} is ready")
        } catch (error: CancellationException) { throw error }
        catch (_: Exception) {
            mutable.value = mutable.value.copy(checking = false,
                message = "Cannot check updates. Check your internet connection and try again.")
        } finally {
            mutable.value = mutable.value.copy(checking = false)
            mutex.unlock()
        }
    }

    suspend fun download() {
        val manifest = mutable.value.available ?: return
        if (!mutex.tryLock()) return
        val file = File(context.cacheDir, "updates/Zaya-Companion.apk")
        try {
            mutable.value = mutable.value.copy(downloading = true, percent = 0, message = "Downloading update…")
            withContext(Dispatchers.IO) {
                file.parentFile?.mkdirs()
                client.newCall(Request.Builder().url(apkUrl).build()).execute().use { response ->
                    check(response.isSuccessful) { "Update download unavailable" }
                    val body = response.body ?: error("Missing APK")
                    body.byteStream().use { input ->
                        file.outputStream().use { output ->
                            val buffer = ByteArray(65536)
                            var received = 0L
                            while (true) {
                                val count = input.read(buffer)
                                if (count < 0) break
                                received += count
                                require(received <= manifest.size) { "Oversized update" }
                                output.write(buffer, 0, count)
                                mutable.value = mutable.value.copy(percent = (received * 100 / manifest.size).toInt())
                            }
                            require(received == manifest.size) { "Incomplete update" }
                        }
                    }
                }
            }
            withContext(Dispatchers.IO) { manifest.verify(file); verifySigner(file, manifest) }
            mutable.value = mutable.value.copy(downloading = false, ready = file, message = "Ready to install")
        } catch (error: CancellationException) { file.delete(); throw error }
        catch (_: Exception) {
            file.delete()
            mutable.value = mutable.value.copy(downloading = false, ready = null,
                message = "Update could not be verified. Check for updates and try again.")
        } finally {
            mutable.value = mutable.value.copy(downloading = false)
            mutex.unlock()
        }
    }

    @Suppress("DEPRECATION")
    private fun installedVersion(): Long {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        return if (Build.VERSION.SDK_INT >= 28) info.longVersionCode else info.versionCode.toLong()
    }

    @Suppress("DEPRECATION")
    private fun verifySigner(file: File, manifest: UpdateManifest) {
        val manager = context.packageManager
        val flags = if (Build.VERSION.SDK_INT >= 28) PackageManager.GET_SIGNING_CERTIFICATES else PackageManager.GET_SIGNATURES
        val current = manager.getPackageInfo(context.packageName, flags)
        val incoming = manager.getPackageArchiveInfo(file.absolutePath, flags)
            ?: throw IllegalArgumentException("Invalid APK")
        require(incoming.packageName == context.packageName) { "Wrong app" }
        val version = if (Build.VERSION.SDK_INT >= 28) incoming.longVersionCode else incoming.versionCode.toLong()
        require(version == manifest.code && version > installedVersion()) { "Wrong update version" }
        val old = if (Build.VERSION.SDK_INT >= 28) current.signingInfo?.apkContentsSigners else current.signatures
        val new = if (Build.VERSION.SDK_INT >= 28) incoming.signingInfo?.apkContentsSigners else incoming.signatures
        require(!old.isNullOrEmpty() && !new.isNullOrEmpty() &&
            old.map { it.toCharsString() }.toSet() == new.map { it.toCharsString() }.toSet()) { "Wrong app signer" }
    }

    fun install(activityContext: Context) {
        val file = mutable.value.ready ?: return
        if (!context.packageManager.canRequestPackageInstalls()) {
            activityContext.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${context.packageName}")))
            mutable.value = mutable.value.copy(message = "Allow updates from Zaya, return here and tap Install update")
            return
        }
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
        activityContext.startActivity(Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION))
    }
}
