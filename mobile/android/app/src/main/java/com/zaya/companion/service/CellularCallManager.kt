package com.zaya.companion.service

import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.ContactsContract
import android.speech.tts.TextToSpeech
import android.telecom.TelecomManager
import android.util.Log
import java.util.Locale

/**
 * Incoming cellular phone call controller and TTS caller identity announcer.
 */
class CellularCallManager(private val context: Context) : TextToSpeech.OnInitListener {

    private val telecomManager by lazy {
        context.getSystemService(Context.TELECOM_SERVICE) as? TelecomManager
    }

    private var tts: TextToSpeech? = null
    private var ttsReady = false

    init {
        try {
            tts = TextToSpeech(context.applicationContext, this)
        } catch (e: Exception) {
            Log.w("CellularCallManager", "TTS initialization failed: ${e.message}")
        }
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale.getDefault()
            ttsReady = true
        }
    }

    fun announceCaller(caller: String) {
        if (!ttsReady) return
        val text = "Incoming call from $caller"
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "CALLER_ANNOUNCE")
    }

    fun answerCall(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            return try {
                telecomManager?.acceptRingingCall()
                true
            } catch (e: Exception) {
                Log.e("CellularCallManager", "Failed to accept call: ${e.message}")
                false
            }
        }
        return false
    }

    fun rejectCall(): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            return try {
                telecomManager?.endCall()
                true
            } catch (e: Exception) {
                Log.e("CellularCallManager", "Failed to end call: ${e.message}")
                false
            }
        }
        return false
    }

    fun resolveContactName(phoneNumber: String): String {
        if (phoneNumber.isEmpty()) return "Unknown"
        return try {
            val uri = Uri.withAppendedPath(
                ContactsContract.PhoneLookup.CONTENT_FILTER_URI,
                Uri.encode(phoneNumber)
            )
            val projection = arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME)
            context.contentResolver.query(uri, projection, null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) {
                    cursor.getString(0) ?: phoneNumber
                } else {
                    phoneNumber
                }
            } ?: phoneNumber
        } catch (e: Exception) {
            phoneNumber
        }
    }

    fun shutdown() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        ttsReady = false
    }
}
