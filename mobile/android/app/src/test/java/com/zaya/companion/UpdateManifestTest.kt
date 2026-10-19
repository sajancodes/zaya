package com.zaya.companion

import com.zaya.companion.updates.UpdateManifest
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.security.MessageDigest

class UpdateManifestTest {
    private fun manifest(bytes: ByteArray): JSONObject = JSONObject()
        .put("version_code", 10001).put("version_name", "0.4.1")
        .put("size", bytes.size).put("sha256", MessageDigest.getInstance("SHA-256")
            .digest(bytes).joinToString("") { "%02x".format(it.toInt() and 255) })

    @Test fun `download must match both the published size and hash`() {
        val bytes = "fixture APK".toByteArray()
        val file = File.createTempFile("zaya-update-", ".apk")
        try {
            file.writeBytes(bytes)
            UpdateManifest.from(manifest(bytes)).verify(file)
            file.writeBytes("changed APK".toByteArray())
            assertThrows(IllegalArgumentException::class.java) { UpdateManifest.from(manifest(bytes)).verify(file) }
            file.writeBytes(byteArrayOf(1))
            assertThrows(IllegalArgumentException::class.java) { UpdateManifest.from(manifest(bytes)).verify(file) }
        } finally { file.delete() }
    }

    @Test fun `invalid release metadata is rejected before downloading`() {
        val bytes = byteArrayOf(1)
        for ((key, value) in listOf("version_code" to -1, "size" to 104857601,
            "version_name" to "../bad", "sha256" to "invalid")) {
            val json = manifest(bytes).put(key, value)
            assertThrows(IllegalArgumentException::class.java) { UpdateManifest.from(json) }
        }
    }
}
