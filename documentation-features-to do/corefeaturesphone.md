📞 Incoming Call Control & Caller Announcer
Native TelecomManager call screening, hands-free answering, call rejection, and TTS caller identity announcer.

Cellular Phone Call Controller (control_incoming_call)
Detects incoming ringing calls, resolves contact names from device contacts (ContactsContract.PhoneLookup), and accepts, rejects, or announces caller identity out loud.

Voice Triggers & Commands
"Who is calling right now?"
"Iris, answer the call."
"Reject the call."
Contacts Directory & Phone Calls (search_contacts, make_phone_call, send_sms_message)
Searches device contacts directory, places cellular calls, or dispatches text messages hands-free.

Voice Triggers & Commands
"Find Alex in my contacts"
"Call Rahul"
"Send an SMS to Rahul saying call me back"

🔔 System Notification Listener & Auto-Responder
Continuous background NotificationListenerService capturing WhatsApp, Instagram, Telegram & SMS with autonomous RemoteInput inline AI auto-replies.

Real-Time System Notification Listener (manage_notification_listener)
Reads incoming WhatsApp, Instagram, Telegram, and SMS notifications in real-time or filters unread messages by application package.

Voice Triggers & Commands
"Read my latest WhatsApp notifications"
"Check if I have any new Instagram messages"
"Summarize my unread notifications"
Autonomous RemoteInput Inline Auto-Reply
Generates intelligent, concise AI responses and sends background inline replies without user interaction or screen unlock.

Voice Triggers & Commands
"Turn on auto-reply mode"
"Disable auto-reply mode"
"Auto-reply to incoming WhatsApp messages"
🎵 System-Wide Media Controller & Deep Link Launcher
System-wide MediaKey intent broadcasts and MediaSessionManager controls across Spotify, YouTube, Apple Music, and podcast players.

System-Wide Media Playback Controller (control_media_playback)
Directly queries and controls active system media sessions (play, pause, toggle, next track, previous track) for Spotify, YouTube, Apple Music, and podcast players.

Voice Triggers & Commands
"Pause the music"
"Skip to the next song"
"Go back to the previous track"
"Toggle playback"
YouTube Playback & Spotify Music Streaming (open_deep_link)
Search and play tracks, videos, genres, or playlists directly inside native YouTube and Spotify apps via deep links.

Voice Triggers & Commands
"Play Believer on YouTube"
"Play synthwave on Spotify"
"Open YouTube and search podcast"
App Launcher & Deep Link Router (open_app, close_app)
Launch any native mobile application installed on your Android device by spoken natural language name.

Voice Triggers & Commands
"Open Settings"
"Launch Instagram"
"Open Chrome"

💬 WhatsApp Messaging Engine
Voice-driven messaging, contact phone number lookup, and automated WhatsApp chat window execution.

WhatsApp Messaging (send_whatsapp_message)
Looks up contact phone number and opens direct WhatsApp chat window pre-filled with the message.

Voice Triggers & Commands
"Send a WhatsApp message to Sidhu saying I'm running 10 minutes late"
"Message Mom on WhatsApp asking what's for dinner"


⚡ Gemini 3.5 Flash Lite & Raw WebSocket Pipeline
Powered by models/gemini-3.5-flash-lite over low-latency raw JSON WebSocket protocol with out-of-band live injection & acoustic echo protection.

Raw WebSocket BidiGenerateContent Engine
Standardized low-latency raw JSON WebSocket protocol over wss://generativelanguage.googleapis.com/... powered by Gemini 3.5 Flash Lite.

Voice Triggers & Commands
"Start real-time voice streaming session"
"Process zero-latency PCM audio stream"
Interruption-Proof Real-Time Injection
Out-of-band live event payload streaming via realtimeInput so background notifications don't break active AI speech generation.

Voice Triggers & Commands
"Inject background notification event live into active stream"
Acoustic Echo Protection
Ultra-early synchronous mic auto-mute and 200ms post-unmute acoustic decay protection eliminating residual echo feedback loops.

Voice Triggers & Commands
"Auto-mute microphone on AI speech output"

⚡ Hardware & System Controls
Instant Android hardware actions, LED flashlight toggles, and direct system settings panel navigation.

Hardware Teleport & Controls (control_device_hardware)
Toggles device hardware (Flashlight) or navigates directly to Wi-Fi, Bluetooth, Location, and Hotspot settings panels.

Voice Triggers & Commands
"Turn on flashlight"
"Turn off flashlight"
"Open Wi-Fi settings"
"Open Bluetooth settings"
📅 Calendar & Memory Management
Scans native OS calendar for 48-hour schedule, creates events, or persists user facts cross-session.

Calendar Scheduling (check_schedule, schedule_new_event)
Check your upcoming Android calendar schedule and create new events or meetings by voice.

Voice Triggers & Commands
"What's on my calendar for today?"
"Schedule a meeting titled Team Sync 2 hours from now for 30 minutes"
Core Memory Vault (save_core_memory, access_core_memory)
Remember user facts, preferences, parking locations, and notes permanently across sessions.

Voice Triggers & Commands
"Remember my car parking spot is level 2"
"What is my car parking spot?"
👁️ Multimodal Screen Vision & Floating Overlay
Live mobile screen capture streaming directly to Gemini Live API with a glassmorphic quick-dock overlay.

Real-Time Screen Capture Vision (screen-capture module)
Stream your live mobile screen directly to IRIS to ask questions about code errors, articles, or images.

Voice Triggers & Commands
"Look at my screen and summarize this article"
"What code error is showing on screen?"
Glassmorphic Floating System Dock (overlay-service module)
Quick-access floating overlay allowing instant voice mute, screen vision toggle, and real-time status monitoring.

Voice Triggers & Commands
"Toggle floating dock"
"Mute voice assistant"
🔒 Security & BYOK Architecture
100% Bring-Your-Own-Key model, local device key encryption, and zero data logging.

Encrypted BYOK Key Vault (ApiKeyService)
Your Gemini API Key is stored encrypted inside Android secure local storage and never leaves your device.

Voice Triggers & Commands
"Enter API key in settings"
Zero Data Logging & Privacy
Sub-second zero-latency PCM audio streams with no recording, tracking, or remote log collection.

Voice Triggers & Commands
"Check privacy & security policy"