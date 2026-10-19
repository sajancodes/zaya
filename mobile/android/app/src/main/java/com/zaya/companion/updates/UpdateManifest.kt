package com.zaya.companion.updates

import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

data class UpdateManifest(val code: Long, val name: String, val sha256: String, val size: Long) {
    fun verify(file: File) {
        require(file.length() == size) { "Update download is incomplete" }
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(65536)
            while (true) { val count = input.read(buffer); if (count < 0) break; digest.update(buffer, 0, count) }
        }
        val actual = digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) }
        require(actual.equals(sha256, ignoreCase = true)) { "Update checksum did not match" }
    }
    companion object {
        fun from(json: JSONObject): UpdateManifest {
            val result = UpdateManifest(json.getLong("version_code"), json.getString("version_name"),
                json.getString("sha256"), json.getLong("size"))
            require(result.code > 0 && result.size in 1..104857600 &&
                result.name.matches(Regex("[0-9][0-9A-Za-z._-]{0,79}")) &&
                result.sha256.matches(Regex("[a-fA-F0-9]{64}"))) { "Invalid app release" }
            return result
        }
    }
}
