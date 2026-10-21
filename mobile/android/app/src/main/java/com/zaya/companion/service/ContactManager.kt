package com.zaya.companion.service

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.ContactsContract
import android.util.Log
import androidx.core.content.ContextCompat

data class PhoneNumberInfo(
    val number: String,
    val typeLabel: String,
    val isPrimary: Boolean = false,
)

data class ContactRecord(
    val contactId: String,
    val displayName: String,
    val numbers: List<PhoneNumberInfo>,
)

sealed class ContactLookupResult {
    data class SingleMatch(val contact: ContactRecord) : ContactLookupResult()
    data class MultipleNumbers(val contact: ContactRecord) : ContactLookupResult()
    data class AmbiguousMatches(val query: String, val candidates: List<ContactRecord>) : ContactLookupResult()
    data class NoNumbers(val contactName: String) : ContactLookupResult()
    data class NotFound(val query: String) : ContactLookupResult()
    data object PermissionRequired : ContactLookupResult()
    data class Failure(val reason: String) : ContactLookupResult()
}

/**
 * Android contacts lookup manager for voice-assisted calling and messaging.
 * Resolves contacts while preserving user privacy (no bulk exporting, no remote sync).
 */
class ContactManager(private val context: Context) {

    companion object {
        private const val TAG = "ContactManager"
        private const val MAX_MATCH_CANDIDATES = 5
    }

    fun hasContactPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.READ_CONTACTS
        ) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * Searches the local device contacts directory for names matching [query].
     */
    fun lookupContact(query: String): ContactLookupResult {
        if (!hasContactPermission()) {
            return ContactLookupResult.PermissionRequired
        }

        val cleanQuery = query.trim()
        if (cleanQuery.isBlank()) {
            return ContactLookupResult.Failure("Contact query cannot be empty.")
        }

        return try {
            val phoneUri = ContactsContract.CommonDataKinds.Phone.CONTENT_URI
            val projection = arrayOf(
                ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER,
                ContactsContract.CommonDataKinds.Phone.TYPE,
                ContactsContract.CommonDataKinds.Phone.LABEL,
                ContactsContract.CommonDataKinds.Phone.IS_SUPER_PRIMARY,
            )

            val selection = "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ? OR ${ContactsContract.CommonDataKinds.Phone.NUMBER} = ?"
            val selectionArgs = arrayOf("%$cleanQuery%", cleanQuery)
            val sortOrder = "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} ASC"

            val contactMap = LinkedHashMap<String, MutableList<PhoneNumberInfo>>()
            val nameMap = LinkedHashMap<String, String>()

            context.contentResolver.query(phoneUri, projection, selection, selectionArgs, sortOrder)?.use { cursor ->
                val idIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.CONTACT_ID)
                val nameIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                val numIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
                val typeIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.TYPE)
                val labelIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.LABEL)
                val primIdx = cursor.getColumnIndex(ContactsContract.CommonDataKinds.Phone.IS_SUPER_PRIMARY)

                while (cursor.moveToNext()) {
                    val id = cursor.getString(idIdx) ?: continue
                    val name = cursor.getString(nameIdx) ?: continue
                    val rawNum = cursor.getString(numIdx) ?: continue
                    val type = if (typeIdx >= 0) cursor.getInt(typeIdx) else ContactsContract.CommonDataKinds.Phone.TYPE_OTHER
                    val customLabel = if (labelIdx >= 0) cursor.getString(labelIdx) else null
                    val isPrimary = if (primIdx >= 0) cursor.getInt(primIdx) > 0 else false

                    val label = resolveTypeLabel(type, customLabel)
                    val phoneInfo = PhoneNumberInfo(
                        number = rawNum.trim(),
                        typeLabel = label,
                        isPrimary = isPrimary
                    )

                    nameMap[id] = name
                    contactMap.getOrPut(id) { mutableListOf() }.add(phoneInfo)
                }
            }

            if (contactMap.isEmpty()) {
                // Check if the contact exists in general Contacts table with 0 phone numbers
                val rawContactName = findContactWithoutNumbers(cleanQuery)
                return if (rawContactName != null) {
                    ContactLookupResult.NoNumbers(rawContactName)
                } else {
                    ContactLookupResult.NotFound(cleanQuery)
                }
            }

            val records = contactMap.map { (id, numbers) ->
                ContactRecord(
                    contactId = id,
                    displayName = nameMap[id] ?: cleanQuery,
                    numbers = numbers.distinctBy { it.number.replace(Regex("[^0-9+]"), "") }
                )
            }

            // Exact name match check to prioritize perfect matches
            val exactMatches = records.filter { it.displayName.equals(cleanQuery, ignoreCase = true) }
            val resolvedList = if (exactMatches.size == 1) exactMatches else records

            when {
                resolvedList.size > 1 -> {
                    ContactLookupResult.AmbiguousMatches(
                        query = cleanQuery,
                        candidates = resolvedList.take(MAX_MATCH_CANDIDATES)
                    )
                }
                resolvedList.size == 1 -> {
                    val record = resolvedList.first()
                    if (record.numbers.size > 1) {
                        ContactLookupResult.MultipleNumbers(record)
                    } else if (record.numbers.size == 1) {
                        ContactLookupResult.SingleMatch(record)
                    } else {
                        ContactLookupResult.NoNumbers(record.displayName)
                    }
                }
                else -> ContactLookupResult.NotFound(cleanQuery)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error looking up contact: ${e.message}")
            ContactLookupResult.Failure("Unable to read contacts: ${e.message}")
        }
    }

    private fun findContactWithoutNumbers(nameQuery: String): String? {
        return try {
            val uri = ContactsContract.Contacts.CONTENT_URI
            val projection = arrayOf(
                ContactsContract.Contacts._ID,
                ContactsContract.Contacts.DISPLAY_NAME,
                ContactsContract.Contacts.HAS_PHONE_NUMBER
            )
            val selection = "${ContactsContract.Contacts.DISPLAY_NAME} LIKE ?"
            val selectionArgs = arrayOf("%$nameQuery%")

            context.contentResolver.query(uri, projection, selection, selectionArgs, null)?.use { cursor ->
                val nameIdx = cursor.getColumnIndex(ContactsContract.Contacts.DISPLAY_NAME)
                if (cursor.moveToFirst()) {
                    cursor.getString(nameIdx)
                } else null
            }
        } catch (e: Exception) {
            null
        }
    }

    /**
     * Resolves display name for an incoming phone number using PhoneLookup.
     */
    fun resolveContactName(phoneNumber: String): String {
        if (phoneNumber.isBlank() || !hasContactPermission()) return phoneNumber

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
            Log.w(TAG, "PhoneLookup failed for incoming number: ${e.message}")
            phoneNumber
        }
    }

    private fun resolveTypeLabel(type: Int, customLabel: String?): String {
        return when (type) {
            ContactsContract.CommonDataKinds.Phone.TYPE_MOBILE -> "Mobile"
            ContactsContract.CommonDataKinds.Phone.TYPE_HOME -> "Home"
            ContactsContract.CommonDataKinds.Phone.TYPE_WORK -> "Work"
            ContactsContract.CommonDataKinds.Phone.TYPE_MAIN -> "Main"
            ContactsContract.CommonDataKinds.Phone.TYPE_CUSTOM -> customLabel?.ifBlank { "Custom" } ?: "Custom"
            else -> "Other"
        }
    }
}
