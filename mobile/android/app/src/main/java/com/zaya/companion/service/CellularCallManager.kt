package com.zaya.companion.service

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.speech.tts.TextToSpeech
import android.telecom.TelecomManager
import android.telephony.PhoneStateListener
import android.telephony.TelephonyCallback
import android.telephony.TelephonyManager
import android.util.Log
import androidx.core.content.ContextCompat
import java.util.Locale

data class IncomingCallInfo(
    val isRinging: Boolean,
    val incomingNumber: String?,
    val callerName: String?,
    val state: Int,
)

sealed class CallOperationResult {
    data class Success(val message: String) : CallOperationResult()
    data class PermissionRequired(val permission: String) : CallOperationResult()
    data object NotRinging : CallOperationResult()
    data class Unsupported(val reason: String) : CallOperationResult()
    data class Failed(val reason: String) : CallOperationResult()
}

sealed class OutgoingCallOutcome {
    data class DialerOpened(val targetName: String, val number: String) : OutgoingCallOutcome()
    data class DirectCallPlaced(val targetName: String, val number: String) : OutgoingCallOutcome()
    data class AmbiguousContact(val query: String, val candidateNames: List<String>) : OutgoingCallOutcome()
    data class MultipleNumbers(val contactName: String, val numbers: List<PhoneNumberInfo>) : OutgoingCallOutcome()
    data class NoNumber(val contactName: String) : OutgoingCallOutcome()
    data class NotFound(val query: String) : OutgoingCallOutcome()
    data class Failed(val reason: String) : OutgoingCallOutcome()
}

/**
 * Incoming cellular phone call controller, telephony listener, outgoing dialer router,
 * and TTS caller identity announcer.
 */
class CellularCallManager(
    private val context: Context,
    val contactManager: ContactManager = ContactManager(context)
) : TextToSpeech.OnInitListener {

    companion object {
        private const val TAG = "CellularCallManager"
        private const val PREFS_NAME = "zaya_call_prefs"
        private const val KEY_CALLER_ANNOUNCEMENTS = "caller_announcements_enabled"
    }

    private val telecomManager by lazy {
        context.getSystemService(Context.TELECOM_SERVICE) as? TelecomManager
    }

    private val telephonyManager by lazy {
        context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
    }

    private var tts: TextToSpeech? = null
    private var ttsReady = false

    @Volatile
    var currentCallState: Int = TelephonyManager.CALL_STATE_IDLE
        private set

    @Volatile
    var currentIncomingNumber: String? = null
        private set

    @Volatile
    var currentCallerName: String? = null
        private set

    @Volatile
    private var hasAnnouncedCurrentCall = false

    private val prefs by lazy {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    private var phoneListener: PhoneStateListener? = null
    private var phoneRegistered = false
    private val mainHandler = android.os.Handler(android.os.Looper.getMainLooper())

    init {
        try {
            tts = TextToSpeech(context.applicationContext, this)
        } catch (e: Exception) {
            Log.w(TAG, "TTS initialization failed: ${e.message}")
        }
        registerTelephonyListener()
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts?.language = Locale.getDefault()
            ttsReady = true
        } else {
            Log.w(TAG, "TTS onInit failed with status code $status")
            ttsReady = false
        }
    }

    // ── Telephony Listener ──────────────────────────────────────────────────

    fun refreshPermissions() { mainHandler.post { registerTelephonyListener() } }

    private fun registerTelephonyListener() {
        if (android.os.Looper.myLooper() != android.os.Looper.getMainLooper()) {
            refreshPermissions(); return
        }
        val tm = telephonyManager ?: return
        val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED
        if (!granted || phoneRegistered) return
        try {
            // The legacy listener still exposes the optional caller number when
            // Android grants READ_CALL_LOG; modern state-only callbacks do not.
            @Suppress("DEPRECATION")
            val listener = object : PhoneStateListener() {
                @Deprecated("Deprecated in Java")
                override fun onCallStateChanged(state: Int, phoneNumber: String?) {
                    handleCallStateUpdate(state, phoneNumber)
                }
            }
            @Suppress("DEPRECATION")
            tm.listen(listener, PhoneStateListener.LISTEN_CALL_STATE)
            phoneListener = listener
            phoneRegistered = true
        } catch (e: Exception) { Log.w(TAG, "Could not register telephony listener", e) }
    }

    fun handleCallStateUpdate(state: Int, incomingNumber: String?) {
        currentCallState = state
        when (state) {
            TelephonyManager.CALL_STATE_RINGING -> {
                if (!incomingNumber.isNullOrBlank()) {
                    currentIncomingNumber = incomingNumber
                    currentCallerName = contactManager.resolveContactName(incomingNumber)
                }
                if (isCallerAnnouncementEnabled() && !hasAnnouncedCurrentCall) {
                    val displayName = currentCallerName ?: currentIncomingNumber ?: "unknown caller"
                    announceCaller(displayName)
                    hasAnnouncedCurrentCall = true
                }
            }
            TelephonyManager.CALL_STATE_OFFHOOK -> {
                // Call answered or in progress — stop announcements
                tts?.stop()
                hasAnnouncedCurrentCall = true
            }
            TelephonyManager.CALL_STATE_IDLE -> {
                // Call ended or missed — reset state
                tts?.stop()
                currentIncomingNumber = null
                currentCallerName = null
                hasAnnouncedCurrentCall = false
            }
        }
    }

    fun getIncomingCallInfo(): IncomingCallInfo {
        refreshPermissions()
        val isRinging = currentCallState == TelephonyManager.CALL_STATE_RINGING
        return IncomingCallInfo(
            isRinging = isRinging,
            incomingNumber = currentIncomingNumber,
            callerName = currentCallerName,
            state = currentCallState
        )
    }

    // ── Caller Announcements ────────────────────────────────────────────────

    fun isCallerAnnouncementEnabled(): Boolean {
        return prefs.getBoolean(KEY_CALLER_ANNOUNCEMENTS, true)
    }

    fun setCallerAnnouncementEnabled(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_CALLER_ANNOUNCEMENTS, enabled).apply()
    }

    fun announceCaller(caller: String) {
        if (!ttsReady || !isCallerAnnouncementEnabled()) return
        val text = when {
            caller.isBlank() || caller.equals("Unknown", ignoreCase = true) -> "Incoming call from a private or unknown number."
            caller.all { it.isDigit() || it == '+' || it == '-' || it == ' ' } -> "Incoming call from $caller."
            else -> "Incoming call from $caller."
        }
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "CALLER_ANNOUNCE")
    }

    // ── Call Controls ───────────────────────────────────────────────────────

    fun answerCall(): CallOperationResult {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return CallOperationResult.Unsupported("Answering calls programmatically requires Android 8.0 (API 26) or higher.")
        }
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ANSWER_PHONE_CALLS) != PackageManager.PERMISSION_GRANTED) {
            return CallOperationResult.PermissionRequired(Manifest.permission.ANSWER_PHONE_CALLS)
        }
        if (currentCallState != TelephonyManager.CALL_STATE_RINGING) {
            return CallOperationResult.NotRinging
        }

        return try {
            telecomManager?.acceptRingingCall()
            tts?.stop()
            CallOperationResult.Success("Answering incoming call.")
        } catch (e: SecurityException) {
            Log.e(TAG, "SecurityException accepting call: ${e.message}")
            CallOperationResult.Failed("Telecom permission denied by system: ${e.message}")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to accept call: ${e.message}")
            CallOperationResult.Failed("Could not accept call: ${e.message}")
        }
    }

    fun rejectCall(): CallOperationResult {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) {
            return CallOperationResult.Unsupported("Declining calls programmatically requires Android 9.0 (API 28) or higher.")
        }
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.ANSWER_PHONE_CALLS) != PackageManager.PERMISSION_GRANTED) {
            return CallOperationResult.PermissionRequired(Manifest.permission.ANSWER_PHONE_CALLS)
        }
        if (currentCallState != TelephonyManager.CALL_STATE_RINGING) {
            return CallOperationResult.NotRinging
        }

        return try {
            @Suppress("DEPRECATION")
            telecomManager?.endCall()
            tts?.stop()
            CallOperationResult.Success("Incoming call declined.")
        } catch (e: SecurityException) {
            Log.e(TAG, "SecurityException declining call: ${e.message}")
            CallOperationResult.Failed("Declining call requires default phone app authorization on this device.")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to end call: ${e.message}")
            CallOperationResult.Failed("Could not decline call: ${e.message}")
        }
    }

    // ── Outgoing Calls ──────────────────────────────────────────────────────

    fun initiateCall(queryOrNumber: String, directCall: Boolean = false): OutgoingCallOutcome {
        val cleanInput = queryOrNumber.trim()
        if (cleanInput.isBlank()) {
            return OutgoingCallOutcome.Failed("Phone number or contact name cannot be empty.")
        }

        // Check if query is directly a phone number (digits and optional leading +)
        val isRawNumber = cleanInput.replace(Regex("[^0-9+]"), "").length >= 3 &&
                cleanInput.all { it.isDigit() || it in "+-() " }

        var targetName = cleanInput
        var targetNumber = cleanInput

        if (!isRawNumber) {
            when (val lookup = contactManager.lookupContact(cleanInput)) {
                is ContactLookupResult.SingleMatch -> {
                    targetName = lookup.contact.displayName
                    targetNumber = lookup.contact.numbers.first().number
                }
                is ContactLookupResult.MultipleNumbers -> {
                    return OutgoingCallOutcome.MultipleNumbers(lookup.contact.displayName, lookup.contact.numbers)
                }
                is ContactLookupResult.AmbiguousMatches -> {
                    return OutgoingCallOutcome.AmbiguousContact(cleanInput, lookup.candidates.map { it.displayName })
                }
                is ContactLookupResult.NoNumbers -> {
                    return OutgoingCallOutcome.NoNumber(lookup.contactName)
                }
                is ContactLookupResult.NotFound -> {
                    return OutgoingCallOutcome.NotFound(cleanInput)
                }
                is ContactLookupResult.PermissionRequired -> {
                    return OutgoingCallOutcome.Failed("Permission to read contacts is required to resolve '$cleanInput'.")
                }
                is ContactLookupResult.Failure -> {
                    return OutgoingCallOutcome.Failed(lookup.reason)
                }
            }
        }

        val sanitizedNumber = targetNumber.replace(Regex("[^0-9+]"), "")
        if (sanitizedNumber.isBlank()) {
            return OutgoingCallOutcome.Failed("Invalid phone number: $targetNumber")
        }

        // Direct call via ACTION_CALL if requested and permitted
        if (directCall && ContextCompat.checkSelfPermission(context, Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED) {
            return try {
                val callIntent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$sanitizedNumber")).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                context.startActivity(callIntent)
                OutgoingCallOutcome.DirectCallPlaced(targetName, sanitizedNumber)
            } catch (e: Exception) {
                Log.e(TAG, "Direct call failed: ${e.message}")
                openDialer(targetName, sanitizedNumber)
            }
        }

        // Safe fallback: open native dialer with prefilled number
        return openDialer(targetName, sanitizedNumber)
    }

    private fun openDialer(name: String, number: String): OutgoingCallOutcome {
        return try {
            val dialIntent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$number")).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(dialIntent)
            OutgoingCallOutcome.DialerOpened(name, number)
        } catch (e: Exception) {
            Log.e(TAG, "Could not open dialer: ${e.message}")
            OutgoingCallOutcome.Failed("Could not open system dialer: ${e.message}")
        }
    }

    fun resolveContactName(phoneNumber: String): String {
        return contactManager.resolveContactName(phoneNumber)
    }

    fun shutdown() {
        mainHandler.post {
            @Suppress("DEPRECATION")
            phoneListener?.let { telephonyManager?.listen(it, PhoneStateListener.LISTEN_NONE) }
            phoneListener = null
            phoneRegistered = false
        }
        tts?.stop()
        tts?.shutdown()
        tts = null
        ttsReady = false
    }
}
