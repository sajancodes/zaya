package com.zaya.companion.data

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * The paired-device secret, sealed with a key that never leaves this phone.
 *
 * The credential is the phone's whole identity to the laptop, so it is not
 * written to disk in the clear and it is not part of the app's backup: a stolen
 * backup of this phone is worth nothing without the Keystore key, which is
 * hardware-backed on most devices and cannot be exported at all.
 */
object SecretBox {
    private const val KEYSTORE = "AndroidKeyStore"
    private const val ALIAS = "zaya.device.secret.v1"
    private const val TRANSFORM = "AES/GCM/NoPadding"
    private const val TAG_BITS = 128
    private const val IV_BYTES = 12

    fun seal(plain: String): String {
        val cipher = Cipher.getInstance(TRANSFORM)
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.doFinal(plain.toByteArray(Charsets.UTF_8))
        val iv = cipher.iv
        return Base64.encodeToString(iv, Base64.NO_WRAP) + ":" +
            Base64.encodeToString(encrypted, Base64.NO_WRAP)
    }

    /** Null when the secret cannot be read back (key rotated, restored backup…). */
    fun open(sealed: String): String? {
        val parts = sealed.split(':')
        if (parts.size != 2) return null
        return try {
            val iv = Base64.decode(parts[0], Base64.NO_WRAP)
            val encrypted = Base64.decode(parts[1], Base64.NO_WRAP)
            if (iv.size != IV_BYTES || encrypted.isEmpty()) return null
            val cipher = Cipher.getInstance(TRANSFORM)
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(TAG_BITS, iv))
            String(cipher.doFinal(encrypted), Charsets.UTF_8)
        } catch (_: Exception) {
            null
        }
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        (store.getEntry(ALIAS, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                // The background service must be able to open this without the
                // owner being present: the phone's own lock screen is the gate.
                .setUserAuthenticationRequired(false)
                .build(),
        )
        return generator.generateKey()
    }
}
