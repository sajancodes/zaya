package com.zaya.companion.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.zaya.companion.protocol.Pairing
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.pairingData: DataStore<Preferences> by preferencesDataStore(name = "zaya_pairing")

/**
 * Where "this phone belongs to that laptop" lives.
 *
 * Pairing survives app restarts, service restarts and phone reboots: the laptop
 * stores its half in SQLite and this half sits behind the Keystore, so a paired
 * phone stays paired until the owner revokes it on either side.
 */
class PairingStore(private val context: Context) {

    val pairing: Flow<Pairing?> = context.pairingData.data
        .catch { emit(androidx.datastore.preferences.core.emptyPreferences()) }
        .map { prefs -> read(prefs) }

    suspend fun current(): Pairing? = pairing.first()

    suspend fun save(pairing: Pairing) {
        val sealed = SecretBox.seal(pairing.secret)
        context.pairingData.edit { prefs ->
            prefs[ADDRESS] = pairing.address
            prefs[DEVICE_ID] = pairing.deviceId
            prefs[DEVICE_NAME] = pairing.deviceName
            prefs[SERVER_NAME] = pairing.serverName
            prefs[SECRET] = sealed
        }
    }

    /** Used when the laptop says the device was revoked, or when the owner forgets it. */
    suspend fun clear() {
        context.pairingData.edit { prefs ->
            prefs.remove(ADDRESS)
            prefs.remove(DEVICE_ID)
            prefs.remove(DEVICE_NAME)
            prefs.remove(SERVER_NAME)
            prefs.remove(SECRET)
        }
    }

    private fun read(prefs: Preferences): Pairing? {
        val address = prefs[ADDRESS]?.trim().orEmpty()
        val deviceId = prefs[DEVICE_ID]?.trim().orEmpty()
        val sealed = prefs[SECRET].orEmpty()
        if (address.isEmpty() || deviceId.isEmpty() || sealed.isEmpty()) return null
        val secret = SecretBox.open(sealed) ?: return null
        if (secret.isEmpty()) return null
        return Pairing(
            address = address,
            deviceId = deviceId,
            secret = secret,
            serverName = prefs[SERVER_NAME]?.takeIf { it.isNotBlank() } ?: "Zaya",
            deviceName = prefs[DEVICE_NAME].orEmpty(),
        )
    }

    private companion object {
        val ADDRESS = stringPreferencesKey("address")
        val DEVICE_ID = stringPreferencesKey("device_id")
        val DEVICE_NAME = stringPreferencesKey("device_name")
        val SERVER_NAME = stringPreferencesKey("server_name")
        val SECRET = stringPreferencesKey("device_secret_sealed")
    }
}
