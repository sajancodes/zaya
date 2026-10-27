package com.zaya.companion.net

import androidx.core.net.toUri

import com.zaya.companion.protocol.Pairing
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.protocol.RemoteFile
import com.zaya.companion.protocol.TaskItem
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

class ApiError(val status: Int, override val message: String) : Exception(message)

sealed interface AuthResult {
    data class Ok(
        val token: String,
        val deviceId: String,
        val deviceSecret: String,
        val serverName: String,
        val protocolVersion: Int,
        val uplinkRate: Int,
        val downlinkRate: Int,
    ) : AuthResult

    /** Wrong key, revoked device, expired key: the owner has to act. */
    data class Denied(val message: String, val retryAfterSeconds: Int = 0) : AuthResult

    /** The laptop is off, the address is wrong, or the network is down. */
    data class Unavailable(val message: String, val status: Int = 0) : AuthResult
}

/**
 * The dashboard's mobile HTTP surface. Same server, same runtime: this is a
 * second way in, never a second Zaya.
 */
class ZayaApi(
    baseUrl: String,
    private val client: OkHttpClient,
) {
    private val base = baseUrl.trimEnd('/')

    /** Short-lived transport token from login/pair. Memory only, never persisted. */
    @Volatile
    var token: String? = null

    suspend fun pair(
        address: String,
        key: String,
        deviceName: String,
        appVersion: String,
    ): AuthResult = authenticate(
        "$address/api/mobile/pair",
        JSONObject()
            .put("key", key.trim().uppercase())
            .put("device_name", deviceName)
            .put("app_version", appVersion)
            .put("platform", "android"),
    )

    suspend fun login(pairing: Pairing, appVersion: String): AuthResult = authenticate(
        "${pairing.baseUrl}/api/mobile/login",
        JSONObject()
            .put("device_id", pairing.deviceId)
            .put("device_secret", pairing.secret)
            .put("app_version", appVersion)
            .put("platform", "android"),
    )

    /** Only the already paired Tailscale host receives the durable credential. */
    suspend fun wakeDesktop(pairing: Pairing): String? = withContext(Dispatchers.IO) {
        val uri = pairing.baseUrl.toUri()
        val host = uri.host.orEmpty()
        if (!host.endsWith(".ts.net", ignoreCase = true)) {
            return@withContext "Starting a closed Zaya requires your laptop's Tailscale address."
        }
        val url = android.net.Uri.Builder().scheme("http").encodedAuthority("$host:8002")
            .path("/wake").build().toString()
        try {
            val body = JSONObject().put("device_id", pairing.deviceId).put("device_secret", pairing.secret)
            val request = Request.Builder().url(url).post(body.toString().toRequestBody(JSON)).build()
            client.newBuilder().followRedirects(false).followSslRedirects(false)
                .callTimeout(10, java.util.concurrent.TimeUnit.SECONDS).build()
                .newCall(request).execute().use { response ->
                    val data = runCatching { JSONObject(response.body?.string().orEmpty()) }.getOrNull()
                    if (response.isSuccessful && data?.optBoolean("ok") == true) null
                    else data?.optString("error")?.ifBlank { null } ?: "The laptop could not start Zaya."
                }
        } catch (_: java.io.IOException) {
            "Could not reach the laptop launcher. The laptop must be on, signed in and connected to Tailscale."
        }
    }

    private suspend fun authenticate(url: String, body: JSONObject): AuthResult =
        withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder()
                    .url(url)
                    .post(body.toString().toRequestBody(JSON))
                    .build()
                client.newCall(request).execute().use { response ->
                    val text = response.body?.string().orEmpty()
                    val json = runCatching { JSONObject(text) }.getOrNull()
                    if (response.isSuccessful && json?.optBoolean("ok") == true) {
                        val audio = json.optJSONObject("audio")
                        AuthResult.Ok(
                            token = json.optString("token", ""),
                            deviceId = json.optString("device_id", ""),
                            deviceSecret = json.optString("device_secret", ""),
                            serverName = json.optString("server_name", "Zaya"),
                            protocolVersion = json.optInt("protocol_version", Protocol.VERSION),
                            uplinkRate = audio?.optInt("uplink_rate", Protocol.UPLINK_RATE)
                                ?: Protocol.UPLINK_RATE,
                            downlinkRate = audio?.optInt("downlink_rate", Protocol.DOWNLINK_RATE)
                                ?: Protocol.DOWNLINK_RATE,
                        )
                    } else {
                        val message = json?.optString("error", "").orEmpty().ifBlank {
                            "The laptop refused that (HTTP ${response.code})"
                        }
                        when {
                            response.code == 429 -> AuthResult.Denied(
                                message,
                                json?.optInt("retry_after", 0) ?: 0,
                            )
                            response.code in 500..599 -> AuthResult.Unavailable(message, response.code)
                            else -> AuthResult.Denied(message)
                        }
                    }
                }
            } catch (error: Exception) {
                AuthResult.Unavailable(friendlyNetworkMessage(error))
            }
        }

    suspend fun snapshot(): JSONObject? = getJson("$base/api/mobile/state")

    suspend fun tasks(): List<TaskItem> {
        val json = getJson("$base/api/mobile/tasks") ?: return emptyList()
        val array = json.optJSONArray("tasks") ?: return emptyList()
        return array.toTaskList()
    }

    suspend fun setOutput(target: String): String? {
        val body = JSONObject().put("target", target)
        val json = postJson("$base/api/mobile/output", body) ?: return null
        return json.optString("target", "").ifBlank { null }
    }

    suspend fun whatsapp(
        action: String,
        chat: String = "",
        query: String = "",
        limit: Int = 15,
    ): JSONObject? = getJson(
        "$base/api/mobile/whatsapp?action=${enc(action)}&chat=${enc(chat)}" +
            "&query=${enc(query)}&limit=$limit",
    )

    suspend fun setWhatsappMode(chatId: String, mode: String): JSONObject? = postJson(
        "$base/api/mobile/whatsapp/mode",
        JSONObject().put("chat_id", chatId).put("mode", mode),
    )?.optJSONObject("result")

    suspend fun files(): List<RemoteFile> {
        val json = getJson("$base/api/mobile/files") ?: return emptyList()
        val array = json.optJSONArray("files") ?: return emptyList()
        val out = ArrayList<RemoteFile>(array.length())
        for (index in 0 until array.length()) {
            val row = array.optJSONObject(index) ?: continue
            val name = row.optString("name", "")
            if (name.isBlank()) continue
            out += RemoteFile(
                name = name,
                size = row.optLong("size", 0L),
                modified = row.optDouble("modified", 0.0),
            )
        }
        return out
    }

    /** Streams a laptop file onto this phone. Returns bytes written. */
    suspend fun download(name: String, destination: File): Long = withContext(Dispatchers.IO) {
        val request = authorized("$base/api/mobile/download?name=${enc(name)}").build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw ApiError(response.code, "Download failed (HTTP ${response.code})")
            }
            destination.parentFile?.mkdirs()
            val body = response.body ?: throw ApiError(response.code, "Download failed: no body")
            body.byteStream().use { input ->
                destination.outputStream().use { output -> input.copyTo(output) }
            }
            destination.length()
        }
    }

    /** Phone file → the laptop's uploads folder, which the runtime can then use. */
    suspend fun upload(displayName: String, body: RequestBody): JSONObject? =
        withContext(Dispatchers.IO) {
            val part = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", displayName, body)
                .build()
            val request = authorized("$base/api/mobile/upload")
                .post(part)
                .build()
            client.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                val json = runCatching { JSONObject(text) }.getOrNull()
                if (!response.isSuccessful || json?.optBoolean("ok") != true) {
                    throw ApiError(
                        response.code,
                        json?.optString("error", "").orEmpty().ifBlank {
                            "Upload failed (HTTP ${response.code})"
                        },
                    )
                }
                json
            }
        }

    suspend fun revokeSelf(deviceId: String): Boolean {
        val json = postJson("$base/api/mobile/revoke", JSONObject().put("device_id", deviceId))
        return json?.optBoolean("ok") == true
    }

    // ── PC ecosystem methods ──────────────────────────────────────────────────

    suspend fun pcStatus(): JSONObject? = getJson("$base/api/mobile/pc/status")

    suspend fun pcAllowedCommands(): JSONObject? = getJson("$base/api/mobile/pc/allowed-commands")

    suspend fun executePcCommand(
        command: String,
        parameters: Map<String, Any?> = emptyMap(),
        confirmed: Boolean = false,
        approvalId: String? = null,
    ): JSONObject? {
        val body = JSONObject().apply {
            put("command", command)
            put("parameters", JSONObject(parameters))
            put("confirmed", confirmed)
            if (!approvalId.isNullOrBlank()) {
                put("approval_id", approvalId)
            }
        }
        return postJson("$base/api/mobile/pc/command", body)
    }

    suspend fun approvePcCommand(approvalId: String): JSONObject? {
        val body = JSONObject().put("approval_id", approvalId)
        return postJson("$base/api/mobile/pc/approve", body)
    }

    suspend fun rejectPcCommand(approvalId: String): JSONObject? {
        val body = JSONObject().put("approval_id", approvalId)
        return postJson("$base/api/mobile/pc/reject", body)
    }

    suspend fun pendingPcApprovals(): JSONArray? {
        val json = getJson("$base/api/mobile/pc/pending-approvals")
        return json?.optJSONArray("approvals")
    }

    suspend fun pcAuditLog(limit: Int = 50): JSONArray? {
        val json = getJson("$base/api/mobile/pc/audit-log?limit=$limit")
        return json?.optJSONArray("entries")
    }

    // ── plumbing ─────────────────────────────────────────────────────────────

    private suspend fun getJson(url: String): JSONObject? = withContext(Dispatchers.IO) {
        client.newCall(authorized(url).get().build()).execute().use { response ->
            readJson(response)
        }
    }

    private suspend fun postJson(url: String, body: JSONObject): JSONObject? =
        withContext(Dispatchers.IO) {
            val request = authorized(url).post(body.toString().toRequestBody(JSON)).build()
            client.newCall(request).execute().use { response -> readJson(response) }
        }

    private fun readJson(response: Response): JSONObject? {
        val text = response.body?.string().orEmpty()
        val json = runCatching { JSONObject(text) }.getOrNull()
        if (!response.isSuccessful) {
            throw ApiError(
                response.code,
                json?.optString("error", "").orEmpty().ifBlank { "HTTP ${response.code}" },
            )
        }
        return json
    }

    private fun authorized(url: String): Request.Builder {
        val builder = Request.Builder().url(url)
        token?.takeIf { it.isNotBlank() }?.let { builder.header("Authorization", "Bearer $it") }
        return builder
    }

    private fun enc(value: String): String =
        java.net.URLEncoder.encode(value, "UTF-8").replace("+", "%20")

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()

        fun friendlyNetworkMessage(error: Throwable): String = when {
            error is ApiError -> error.message
            error is java.net.UnknownHostException ->
                "Can't find that laptop address. Is Tailscale connected?"
            error is java.net.ConnectException ->
                "Nothing answered at that address. Is Zaya running on the laptop?"
            error is javax.net.ssl.SSLException ->
                "The certificate didn't match. Use the laptop's Tailscale name over HTTPS."
            error is java.net.SocketTimeoutException -> "The laptop did not answer in time."
            else -> error.message ?: error.javaClass.simpleName
        }

        /** Kept separate so tests can exercise it without a network stack. */
        fun parseTasks(array: JSONArray): List<TaskItem> = array.toTaskList()
    }
}

private fun JSONArray.toTaskList(): List<TaskItem> {
    val out = ArrayList<TaskItem>(length())
    for (index in 0 until length()) {
        val row = optJSONObject(index) ?: continue
        val task = TaskItem.from(row)
        if (task.taskId.isNotBlank()) out += task
    }
    return out
}
