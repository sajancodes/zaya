# Phone chat and owner-requested access

The optimistic phone message and both laptop echoes now carry the same request ID.
Sending a request to the live model acknowledges delivery; it does not mark an
unverified action as executing or completed. Real task progress remains separate.

On an answered owner-initiated call, the live model receives a request to greet
the owner naturally and ask what he needs. There is no prerecorded greeting or
fixed spoken line. Incoming calls from Zaya keep their event briefing and the
isolated handling of external WhatsApp text. The existing 5–10 second answer
delay and phone microphone routing remain in place.

Settings > Phone access opens Android's contacts and shared-media permissions.
The owner may choose selected photos rather than the full library. Permissions
are also requested on demand. Granting a permission never approves a call or SMS;
the existing separate communication confirmation remains required.

The owner-only `browse_phone_media` tool searches up to ten shared photos, videos
or audio items by filename and opens a returned content URI on the phone. It
returns metadata, not file bytes or visual descriptions. Private app storage is
not exposed. Nothing scans or uploads the entire library in the background.

`make_phone_call` accepts `app=whatsapp`. Contact lookup preserves ambiguous-name
and multiple-number choices. With phone confirmation, the app opens WhatsApp's
registered voice-call action for the selected contact/number, when available.
An opened activity is not reported as an answered call. Missing registrations
are reported as unsupported rather than guessing an undocumented call URL.

Focused verification: inline Python checks exercise the actual command relay
and call-answer hook with fake sessions, preserving message identity, one
delivery, acknowledgement state, generated greeting and incoming briefing.
Android Kotlin compilation and release lint/build cover the Android changes.
No physical Android device is attached; live WhatsApp behavior, permission dialogs
and audible greetings still require owner verification on the phone.
