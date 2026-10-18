# `services/`, `memory/`, `dashboard/` — companion, WhatsApp, persistence, dashboard

Developer reference for the runtime surfaces around the Gemini Live session of **Zaya** (Windows desktop voice assistant by Sajan Rai): the desktop companion (`services/zayabar.py`, `services/companion_bubble.py`, `services/desktop_windows.py`), the Hermes-backed WhatsApp stack (`services/whatsapp/*`), local persistence (`memory/*`) and the phone dashboard (`dashboard/server.py` + `dashboard/static/*`).

Line references are `path:line` into this repository. Configuration **key names**, JSON shapes and SQLite columns are reproduced; no API keys, bearer tokens, linked-device credentials, session keys or personal chat content appear here.

---

## 1. Companion bar

| File | Class | Notes |
|---|---|---|
| `services/zayabar.py` | `ZayaBar(QWidget)` | Frameless `Tool` + `WindowStaysOnTopHint`, translucent, `WA_ShowWithoutActivating` (`services/zayabar.py:25-27`); created only on the Qt thread (`ui.py:5839-5847`). |
| `services/companion_bubble.py` | `CompanionBubble(QWidget)` | Cloud-shaped caption; `WindowTransparentForInput`, `WA_TransparentForMouseEvents` (`companion_bubble.py:16-21`). |
| `services/desktop_windows.py` | `DisplayWindow(QDialog)` | Generic assistant-created display; closes with its parent, re-runs a `fit` on resize (`desktop_windows.py:11,22-25`). |
| `core/zayabar_config.py` | `load_config`, `asset_path`, `local_path` | Validation and asset resolution for `zayabar.json`. |

Signals (`zayabar.py:18-22`): `state_changed(str)`, `runtime_event(dict)`, `reaction_requested(str)`, `reaction_audio_active(bool)`, `config_reloaded()`.

### 1.1 States

`base_state` arrives through `state_changed` → `set_state()` (`zayabar.py:46,117-125`); the main window's applied-state signal is forwarded in by the UI shim (`ui.py:5842`, emitter `ui.py:2970,5762`), so the bar sees the same LISTENING / THINKING / SPEAKING / CONNECTING values as the HUD. Rendered `mode` is derived with fixed precedence (`zayabar.py:201-203`):

```
poked    monotonic() < poked_until
talking  base_state == 'SPEAKING'
thinking base_state == 'THINKING' or active_tasks non-empty
standby  otherwise
```

`load_media()` uses `asset_path(config, mode, emotion)` outside `talking`, and `assets.talking[emotion]` (→ `talking/neutral` → `standby`) for `talking` (`core/zayabar_config.py:84-92`). GIFs load through an in-memory `QBuffer`/`QMovie` scaled to the widget (`zayabar.py:257-270`), images through `QPixmap` (`271-274`); missing or unreadable media paints a fallback rect with `'Zaya\nAdd your images in zayabar.json'` (`283-294`). Emotions change on the bus (`avatar.emotion`, published by `actions/avatar_expression.py:13`) and only names in `EMOTIONS` are accepted (`core/zayabar_config.py:7`).

### 1.2 Poke playback

- Double-click selects a random reaction, rate-limited by `reaction_cooldown_seconds` (`zayabar.py:296-302`). Reactions come from `poke_reactions`, or are synthesised from `reaction_lines` with the `poked` image and no audio (`133-135`).
- `preload_reactions()` measures each WAV from its header (`int(1000*nframes/framerate) + 150`) and builds one `QSoundEffect` per reaction (`127-149`); non-`.wav` audio is rejected by validation (`core/zayabar_config.py:50-51`).
- `play_reaction()` holds the poked pose for `max(reaction_duration_ms, measured)`, arms the one-shot `restore_timer`, reloads media and shows a `poke` bubble (`154-162`). While the bar is `SPEAKING`, the reaction is stashed in `pending_reaction` and replayed when `set_state()` next sees a non-SPEAKING state (`163-165`, `123-125`).
- Otherwise the WAV plays and `reaction_requested` fires (`166-177`); a missing file still emits the text, an unloadable one logs a hint (`174-177`).
- `playingChanged` → `reaction_audio_active` → `ui.py:5844` → `main.companion_audio_activity` (`main.py:1440-1446`), which ducks the render sessions and blocks the mic path while active (`main.py:1624-1627`).
- `reaction_requested` → `ui.py:5843` → `main.companion_reaction` (`main.py:1437-1438`) logs `'Zaya: <line>'`; the log is wired back to the bar (`ui.py:5845` → `observe_log`, `zayabar.py:213-215`), which shows it as a `reply` bubble — a poke without audio still produces a caption through that loop.

### 1.3 Positioning

`position_on_taskbar()` runs on a 1500 ms timer and after a drag (`zayabar.py:57-60,94-115`): `floor = full.bottom() + 1`; `edge = work.bottom() + 1` when a taskbar reserves space, else `floor - 48`. With `fit_legs_to_taskbar` the height is scaled so the seat line lands on the taskbar edge via `seat_fraction`, clamped ≥ 32 px, width kept proportional to `width/height`. `x = full.left() + (full.width() - width) * horizontal_position`; `y = min(floor - height - 2, edge - height * seat_fraction)`, clamped to the screen top. `screen_index` is read directly and an invalid value falls back to the primary screen (`97-99`) — this key is not validated by `zayabar_config`. Dragging updates `horizontal_position` live and persists it to `memory/zayabar_state.json` (`304-323`), restored over the config at startup (`31-36`). The bubble sits above the sprite at `x + width/2 - 0.78*bubble_width`, clamped 4 px inside the available geometry (`230-237`).

### 1.4 `zayabar.json` (validated in `core/zayabar_config.py:17-67`)

| Key | Type / range | Default |
|---|---|---|
| `enabled`, `show_main_window_on_start`, `fit_legs_to_taskbar`, `poke_audio_enabled` | bool | true / false / true / true |
| `width`, `height` | 64–600 | 240 |
| `seat_fraction` | 0.1–0.95 | 0.6 |
| `horizontal_position` | 0–1 | 0.82 |
| `screen_index` | int (widget-level, unvalidated) | 0 |
| `reaction_cooldown_seconds` | 2–120 | 10 |
| `reaction_duration_ms` | 500–10000 | 2200 |
| `reaction_lines` | non-empty strings ≤160 | — |
| `poke_reactions` | ≤30 × `{text ≤160, image, audio(.wav)}` | falls back to `reaction_lines` |
| `assets` | `{standby, thinking, poked, talking:{neutral,happy,sad,angry,surprised}}` | — |
| `emotion_tones` | per-emotion voice text ≤500 | `DEFAULT_TONES` (`zayabar_config.py:8-14`) |
| `bubble_max_characters` | 32–1000 | 140 |
| `bubble_duration_ms` | 1000–30000 | 6500 |
| `bubble_max_width` | 140–600 | 300 |
| `audio_ducking` | normalised by `core/audio_ducking.settings` | `{enabled, background_ratio, voice_volume, release_seconds}` |

Paths resolve relative to the config file unless absolute (`core/zayabar_config.py:77-81`), so a hand-edited config can point at any local file. The in-app editor validates JSON, writes a `.tmp` sibling, loads it once and only then replaces the real file (`zayabar.py:340-370`).

### 1.5 Bus subscriptions and bubble

The bar subscribes to **every** event — `bus.subscribe('*', self.runtime_event.emit)` (`zayabar.py:48`) — so publishers stay on their own threads and Qt queues the slot onto the GUI thread. `on_runtime` (`179-199`):

| Event | Effect |
|---|---|
| `avatar.caption` | `reply` bubble (model output transcription, `main.py:1889-1890`) |
| `avatar.reaction.playing` | extends `poked_until` by `min(10000, max(reaction_duration_ms, duration_ms))`; **no publisher exists in this repo** — currently dead code |
| `avatar.emotion` | updates `emotion` when known, reloads media |
| `task.*` | `task_id = task['task_id'] or task['id']`; `created`/`executing`/`verifying` add to `active_tasks`, anything else removes (`191-199`) |

`show_bubble()` truncates through `shorten()` to `bubble_max_characters` (`'........'` suffix, `companion_bubble.py:7-11`), auto-hides after `bubble_duration_ms`, and keeps `thinking` bubbles until the mode changes (`zayabar.py:217-228`). The context menu offers Settings, Gemini keys, character configuration, reload, mute, show and Close (`63-73`), mirrored by a tray icon when a system tray exists (`74-83`). `shutdown()` closes menu and bubble, stops every sound and timer, and unsubscribes (`372-387`).

---

## 2. WhatsApp end-to-end

### 2.1 Modules

| File | Role |
|---|---|
| `service.py` | `WhatsAppService` facade: ingestion, inbox queries, delivery, 10 s supervisor; module-level `get_service()` bound to `memory/zaya_runtime.db` (`service.py:170-175`). |
| `pairing.py` | `PairingManager` — QR pairing via Hermes `bridge.js`; writes the private session pointer. |
| `native_bridge.py` | `NativeBridge` — owns/spawns the Hermes HTTP bridge on `127.0.0.1:8768`; polls `/messages`, posts `/send`. |
| `bridge.py` | `HookReceiver` (authenticated loopback hook sink) + `install_hook()` (reversible installer). |
| `hook_handler.py` | Standalone Hermes hook: key whitelist, SQLite outbox, loopback-only POST. |
| `hermes_adapter.py` | `HermesAdapter` — transport-or-CLI delivery with durable request-id dedup. |
| `store.py` | `WhatsAppStore` — schema, unread counts, modes, alerts, idempotent sends. |
| `models.py` | `Message`, `validate_chat_id`, `normalize_hook`. |
| `policy.py` / `importance.py` / `handler.py` | Reply gate + generator / semantic classifier / `ReplyWorker` pipeline. |
| `connection.py` / `ui.py` | Pointer verification / `WhatsAppConnectionDialog` QR panel (QR images never enter model context). |
| `actions/whatsapp.py` | Owner-facing `whatsapp` tool (`require_owner()` first line). |
| `core/proactive_manager.py` | Voice notification selector (relay / inbox / alert). |

### 2.2 Pairing and the saved session pointer

1. The panel polls `PairingManager.status()` every 500 ms and runs `start()` on a worker thread (`ui.py:39-46,48-62`).
2. `start()` requires `node`, `bridge.js` under `<hermes_home>/hermes-agent/scripts/whatsapp-bridge/` (or `~/hermes-agent/...`) and a sibling `node_modules` (`pairing.py:44-49`).
3. If `<session>/creds.json` already holds `me.id`, the pointer is saved from those credentials and **no new QR is produced** — an existing linked identity is never erased to mint a QR (`pairing.py:50-57`).
4. Otherwise it spawns `bridge.js --pair-only --pair-json --session <session>` with `WHATSAPP_MODE='self-chat'`, `WHATSAPP_DM_POLICY='pairing'`, `HERMES_HOME=<home>`, no window (`58-63`), plus a 300 s cancellation timer (`65-68`).
5. The watcher parses JSON lines (`97-125`): `qr` → `qrcode.make()` PNG at `config/hermes_pairing_qr.png` (git-ignored), state `waiting_scan`; `connected` → 2.5 s grace for Hermes to flush credentials, then `_save_connection(user)`; `error` → generic message. Any other ending records `failed`, never a false success.
6. `_save_connection` (`71-95`) re-reads `creds.json`, normalises the account id (`account:device` → `account`, `connection.py:8-12`), refuses a mismatch with the connected account, then atomically writes `config/hermes_connection.json`: `{hermes_home, session_path, account_id, account_name, mode: 'self-chat', paired_at, credentials_saved}`. It also ensures `WHATSAPP_ENABLED=true` and `WHATSAPP_MODE=self-chat` in `<hermes_home>/.env`, deletes the QR PNG and publishes `whatsapp.connection.changed`.
7. `load_connection()` (`connection.py:15-32`) treats the file as private: the session directory must live inside `hermes_home` and contain `creds.json`, and `account_id` must equal the credential identity. Keys are never copied out of Hermes.

### 2.3 Transport selection and components

```
Zaya owns the session                          Hermes gateway/CLI owns the session
NativeBridge, HTTP 127.0.0.1:8768              HookReceiver + installed hook
GET /health, GET /messages (consumes queue)    POST /events (bearer), 5 hook events
POST /send                                     observation only, complete=false
outgoing: adapter.transport ─┐
                             └─► HermesAdapter.send() ── else ─► `hermes send --file -`
```

- **Owned native bridge** (preferred). `service.connect_live()` builds `NativeBridge(self.ingest, connection)` (`service.py:52-70`). `start()` (`native_bridge.py:113-169`) refuses to run when `<hermes_home>/gateway.pid` names a live process (Zaya never disturbs a user-run gateway), takes an exclusive lease on `<session>/zaya-bridge.lock` via `msvcrt.locking`/`flock` so only one Zaya instance monitors (`94-111`), then either attaches to an already-listening bridge it can *prove* it owns (`verified_orphan`, `35-57`: single listening pid, `bridge.js` path, `--session`, `--port`, no live parent) or spawns it. Poll loop: `/health` → `ready = status == 'connected'`, then `/messages`; unsupported events are skipped, and no attachment path is ever opened (`171-198`). `send()` POSTs `{chatId, message, replyTo?}` with a 50 s timeout (`200-211`). Process env is observation-oriented: `WHATSAPP_MODE=bot`, `WHATSAPP_ALLOWED_USERS='*'`, `WHATSAPP_DM_POLICY=open`, `WHATSAPP_FORWARD_OWNER_MESSAGES=true`, `WHATSAPP_SEND_READ_RECEIPTS=false`, empty `WHATSAPP_REPLY_PREFIX` (`156-158`).
- **Observation hooks** (gated session). `HookReceiver` (`bridge.py:18-76`) listens on an ephemeral loopback port with a random `secrets.token_urlsafe(32)` secret, accepts only `POST /events`, rejects any request carrying an `Origin` header, compares the bearer with `hmac.compare_digest`, caps bodies at 64 KiB and whitelists five Hermes events. The `{url, token}` pair is published to `config/hermes_bridge.json` and removed on clean shutdown when it still matches — ephemeral and git-ignored. `install_hook()` (`88-98`) copies `hook_handler.py` into `<hermes_home>/hooks/zaya-whatsapp/` (backing up a differing previous copy), writes `HOOK.yaml` declaring `gateway:startup` / `session:*` / `agent:*`, and points `zaya-path.json` at the descriptor. The hook imports nothing from Zaya: it whitelists ten context keys, buffers to a local `zaya-hook-outbox.db` (7-day retention), requires the descriptor URL to be `http://127.0.0.1/events`, flushes ≤100 events with a 0.75 s timeout and deletes only on `204` (`hook_handler.py:15-44`). A `gateway:startup` hook **closes the native bridge** and downgrades to observation (`service.py:85-91`).
- **Hermes CLI fallback.** `_command()` resolves `hermes` on `PATH`; on Windows a `.cmd`/`.bat` launcher is first asked for its native argv (`hermes --print-runtime-command send`) so contact text never crosses `cmd.exe` quoting (`hermes_adapter.py:22-39`). Sends run `hermes send --to whatsapp:<chat_id> --json --file -` with the body on stdin, 60 s timeout (`67-68`).

Only the native bridge yields a complete feed; the status query says so explicitly — `full_inbox_available: False`, plus `complete_live_events_available`, `automatic_reply_feed_ready`, `manual_outgoing_scope: 'direct chats only'` (`service.py:114-132`). Hook messages carry `complete=False` and `source='hermes_hook'` (`models.py:39-51`) and are refused by the auto-reply path twice (`handler.py:60`, `policy.py:7`).

### 2.4 Store schema (`memory/zaya_runtime.db`)

Created in `WhatsAppStore.__init__` (`store.py:22-50`); the same file also hosts the task runtime's `runtime_tasks` and `tool_results` (`core/task_runtime.py:126`). WAL + `busy_timeout=5000`, one connection shared across threads behind an `RLock` (`store.py:17-21`).

| Table | Columns | Notes |
|---|---|---|
| `wa_contacts` | `contact_id` PK, `display_name`, `aliases_json`, `priority`, `notes`, `first_seen_at`, `last_seen_at`, `name_verified` | migration adds `name_verified` (`45-49`); a verified name is never overwritten by push-names (`119-124`) |
| `wa_chats` | `chat_id` PK, `title`, `chat_type` (`dm`/`group`), `mode`, `ai_active`, `started_at`, `paused_at`, `last_message_at`, `unread_count`, `last_manual_owner_message_at`, `last_ai_message_at` | modes `observe, draft, auto, manual, paused` (`MODES`, `store.py:10`); `ai_active` mirrors `auto` |
| `wa_messages` | `message_id` PK, `chat_id`, `sender_id`, `direction`, `source`, `text`, `timestamp`, `received_at`, `handled`, `reply_to_id`, `ai_generated`, `transport_status`, `complete`, `draft`, `notified_at` | index `wa_message_chat_time(chat_id, timestamp)` (`35`); `handled` = auto-reply claim, `draft` = preview, `notified_at` = already announced |
| `wa_alerts` | `alert_id` PK, `chat_id`, `message_id` UNIQUE, `score`, `category`, `reason`, `created_at`, `delivered_at`, `acknowledged_at`, `notify_owner` | one alert per message (`alert-<message_id>`), `INSERT OR IGNORE` (`195-199`) |
| `wa_send_intents` | `request_id` PK, `chat_id`, `text`, `status`, `message_id`, `detail`, `created_at` | transport idempotency (`pending` → `accepted`/`failed`/`unknown`) |
| `wa_settings` | `key` PK, `value` | `default_dm_mode` (`153-155`), `alerts_muted_until` (`proactive_manager.py:16-19`) |
| `wa_chat_aliases` | `alias` PK, `chat_id` | JID canonicalisation |

- **Dedup.** `ingest()` returns `False` when `message_id` already exists (`store.py:103-110`); bus fan-out and worker enqueue happen only on a real insert (`service.py:96-104`). Hook messages dedup on `sha256([event, session_id, chat_id, user_id, text])` with a `hook-` prefix (`models.py:46-51`) because installed hooks expose truncated inbound text and no raw id.
- **Alias / canonicalisation.** `link_alias()` (`store.py:57-79`) unifies an LID chat with its phone-number JID only when the native event established that relation (`native_bridge.py:67-70`); it merges unread counts, preserves an owner takeover mode, moves `wa_messages`/`wa_alerts`/`wa_send_intents` rows and rewrites downstream aliases. Every public method starts with `canonical_chat()` (`52-55`), so a chat has one id everywhere.
- **Modes.** Per chat, `set_mode()` (`140-151`) — switching to `auto` stamps `notified_at` on all pending rows so old previews are never read aloud later. Globally, `set_global_mode()` (`157-175`) allows only `auto`/`observe`, applies to non-`paused` `chat_type='dm'` rows, never to groups, and returns `replays_history: False`. New DMs inherit the global mode only when it is already `auto` (`115-118`); groups always start in `observe`.
- **Manual takeover.** Any non-AI outgoing message sets `mode='manual'`, `ai_active=0` and refreshes `last_manual_owner_message_at` (`store.py:133-137`); AI rows only touch `last_ai_message_at`.
- **Ingest side effects** (`111-138`): contact and chat upsert (`title` from the incoming display name unless verified), unread increment, `notified_at` stamping while the chat is `auto`.
- **Send reservation.** `reserve_send()` is `INSERT OR IGNORE` on `request_id` (`201-203`); the adapter checks the intent table *before* reserving (`hermes_adapter.py:47-55`), so a repeated request id returns the earlier result with `deduplicated: True` instead of resending. `finish_send()` stores `accepted`/`failed`/`unknown` (`205-207`). Accepted requires `returncode == 0` **and** `success is true` **and** a non-empty `message_id` **and** no `error` (`hermes_adapter.py:69-79`); that row is also ingested as an outgoing `ai_generated` message (`75-76`). Text is refused when empty, >20 000 chars, without a request id, or containing `MEDIA:`/`[[` (`43-46`).
- **Chat resolution.** `resolve_chat()` accepts an exact JID validated by `[0-9A-Za-z_.+-]{1,100}@(s.whatsapp.net|g.us|lid)` (`models.py:9-12`) or an exact unique case-insensitive `title` (`service.py:106-112`); ambiguity raises rather than guessing.

### 2.5 Classification, policy, handler

```
incoming (complete, source != hermes_hook)
  │ ReplyWorker.process(): trust_context = TRUST_EXTERNAL_MESSAGE      handler.py:37
  │ pool of 2, semaphore 50, per-chat lock                            handler.py:15-16,39-43
  ▼ importance.classify() → {score, category, reason, needs_owner, notify_owner}   importance.py:6-32
  ▼ store.alert() when score ≥ 40 or needs_owner or relay              handler.py:56-58
  ▼ mode gate: mode ∈ {draft, auto} AND complete AND source != hermes_hook        handler.py:60
  ▼ may_reply() for auto: needs_owner false AND score < 70             policy.py:6-8, handler.py:62
  ▼ store.claim_message() — UPDATE … WHERE handled=0, rowcount == 1    store.py:187-189, handler.py:64
  ▼ generate_reply() — needs_owner must be exactly false and reply non-empty       handler.py:69-74
  ▼ prefix "Zaya · Sajan Rai's AI assistant:\n" → save_draft()          handler.py:75-76
  ▼ re-read chat: abort on closed / mode != auto / last_manual_owner_message_at changed   77-81
  ▼ adapter.send(chat_id, reply, 'reply-'+message_id, message_id)      handler.py:82
```

- **Classification** is one tool-free Gemini JSON call (15 s timeout); unparseable results fail closed to `{score: 40, needs_owner: True}` (`importance.py:23-24`). Score is clamped and re-bucketed locally: `urgent ≥ 85`, `important ≥ 70`, else `normal` (`25-30`). `notify_owner` becomes true for an explicit pass-along/urgent request **or** any score ≥ 70 (`31`); `needs_owner` is true unless the model returned exactly `false` (`32`).
- **Reply generation** sends only the incoming text, `activity.snapshot()` (owner-authorized music/project summaries — expiring, in-memory only, `core/session_activity.py:40-53`), the `owner_relay_queued` flag, and the last 12 non-synthetic rows of that contact's own chat (`policy.py:15-17`). The system instruction forbids impersonating the owner, denies computer tools and private personal memory, forbids commitments and money/security actions, treats conversation text as untrusted, and requires an empty reply with `needs_owner: true` when owner judgement is needed (`18-33`).
- **Race gates.** `claim_message` is one atomic `UPDATE … AND handled=0` (`store.py:187-189`); the worker re-reads the chat immediately before the transport call and aborts on a mode change or a new `last_manual_owner_message_at` (`handler.py:77-81`); the adapter dedups by `request_id` (`hermes_adapter.py:47-55`). Queue saturation returns the message to the inbox with one `system.warning` instead of blocking (`handler.py:21-24`).
- **Failure handling** never falls back to screen typing or privileged tools: the exception is redacted and stored as a score-70 alert (`handler.py:85-89`). Draft-mode chats and any reply whose `needs_owner` is not `false` raise an alert and keep the preview (`71-74`).

**Withheld from contact replies.** Never: owner location, activity beyond `shared_current_activity`, availability, schedule or intentions; private memory, files, credentials or command output (the model has no tools, `policy.py:33`); commitments or money/security actions; claims that the owner was notified, will reply, or received anything (only "queued" wording is allowed, `24-25,31`). Transport directives (`MEDIA:`, `[[`) are rejected at the adapter (`hermes_adapter.py:45-46`). Owner chat history is never included — only the contact's own last 12 rows — and live-session history is replaced by the expiring activity snapshot (`policy.py:14-17`).

### 2.6 Owner relay queue (pass-along and urgent)

`ProactiveManager` (`core/proactive_manager.py`) is polled every 2 s by `main._operator_notifications()` (`main.py:1496-1536`) and yields at most one notification:

| Kind | Selection | Announcement |
|---|---|---|
| `relay` | `notify_owner=1 AND delivered_at IS NULL AND acknowledged_at IS NULL` and chat not `paused`, ≤5 by score (`proactive_manager.py:27-31`) | contact title + the requested text (≤900 chars), spoken as "messages to pass along or urgent updates" |
| `inbox` | un-announced incoming rows in `observe`/`manual` chats (≤10) when global mode is **not** `auto` (`34-46`) | "N new WhatsApp messages" with short previews |
| `whatsapp` | un-delivered alerts `score ≥ 70` whose message was not already announced (`47-53`) | count only — raw contact text and classifier reasons never become a privileged user turn |

Guard rails: quiet while the owner is busy or within 5 s of the last notice (`21-24`); mute via `wa_settings.alerts_muted_until`, capped at 24 h (`16-19`); with global `auto` the ordinary inbox channel is silenced and pending previews are stamped `notified_at` locally so stopping auto cannot replay a backlog (`32-39`). Delivery goes through `core/notification_voice.synthesize_notice()` — an isolated tool-free Live session — and the item is marked delivered only after the audio is queued (`main.py:1515-1528`), so a failed synthesis stays retryable (`1529-1533`). Reply generation is told the relay is queued so the contact hears "queued", never "passed on" (`handler.py:66-68`, `policy.py:24-25`).

---

## 3. Memory and persistence

### 3.1 `memory/conversation.db` (`memory/conversation_store.py`)

| Table | Columns |
|---|---|
| `state` | `key` PK, `value` — `chat_id` (uuid4 hex on first init, `:31`), `handle`, `scope`, `handle_at`, `operator_scope`, `operator_goal` |
| `messages` | `id` PK, `role` (`user`/`model`), `text`, `created` |

- `append(role, text)` — validated roles, whitespace-stripped, returns the row id (`:75-82`). `record(role, text, ident)` rewrites an already-inserted live row with the final text (`:84-91`).
- `recent(limit=40, max_chars=32000)` — newest-first, ≤100 rows, trimmed from the front to fit the character budget, returned oldest-first (`:93-104`). Prompt size is bounded; storage is not.
- `search(query, limit=12)` — escapes `\`, `%`, `_` and uses `LIKE … ESCAPE '\'`; ≤40 rows, text cut to 2000 chars (`:106-112`). `restore_content()` wraps recent history in a `[SAVED CONVERSATION — HISTORICAL CONTEXT ONLY]` user turn stating nothing in it is a new command (`:114-124`).
- **Resume scope** — `resume_scope(model, voice, api_key)` hashes `[RESUME_PROTOCOL='zaya-live-3', model, voice, api_key]`, the key contributing only as hash input (`:16-20`). `save_handle/handle/clear_handle` accept a stored session handle for at most `HANDLE_SECONDS = 2 h` and only for the identical scope (`:59-73`); `main.py:2512-2518` recomputes the scope on every connect and drops the handle when model/voice/key changed — this is what keeps handles from the pre-recovery stall bug from being reopened (`:14-16`).
- **Operator scope/goal** — each owner turn calls `_begin_owner_goal()` (`main.py:1221-1233`), which stores a fresh `uuid4().hex` scope and a redacted ≤300-char goal into `state`, then derives `request_id = f"{scope}:{tool}:{sha256(args)}"` for the operator/task-runtime dedup cache (`main.py:1245-1252`).

### 3.2 `config/api_keys.json` (`memory/config_manager.py`) — key names only

| Key | Accessor | Notes |
|---|---|---|
| `gemini_api_key`, `gemini_api_keys` | `save_api_keys` / `get_gemini_key` | `parse_keys` normalises the list; the first entry is duplicated into the singular key (`:20-40`); `is_configured()` requires length > 15 (`:54-56`) |
| `user_name` | `get_user_name` / `save_assistant_config` | assistant name is pinned to `Zaya` (`:59-80`) |
| `voice_name` | `get_voice` / `save_voice` | must be in `AVAILABLE_VOICES`; unknown collapses to `DEFAULT_VOICE` (`:86-109`) |
| `wake_word_enabled` | get/save | local wake-word gating (`:112-126`) |
| `push_to_talk_enabled` | get/save | mic closed unless the chord is held (`:129-135`) |
| `auto_execute_owner` | get/save | saved boolean opt-in only; the setter raises `PermissionError` unless `trust_context` is `TRUST_LOCAL_OWNER` (`:138-150`) |
| `thinking_enabled` | get/save | off by default (`:178-189`) |
| `turn_tuning` | get/save | `{enabled, silence_ms 200-3000, prefix_ms 0-1000, end_sensitivity, start_sensitivity}` (`:192-238`) |
| `proactive_audio` | get/save | opt-in selective audio (`:241-253`) |
| `media_resolution` | get/save | `default\|low\|medium\|high` (`:256-270`) |
| `hud_style` | get/save | `face` or `core` (`:153-170`) |
| `morning_brief_enabled` | get/save | default true (`:286-299`) |
| `input_device`, `output_device` | get/save | device **names**, `''` = system default (`:302-341`) |
| `plugins_enabled` | get/save | per-plugin bool, default enabled (`:344-346,389-402`) |
| `plugin_config` | `get_plugin_config`, `get_plugin_setting`, `save_plugin_config` | `plugin_config[namespace][key]`, merged per write (`:349-387`) |

Keys present in the live file but written elsewhere: `os_system`, `preferred_browser`, `ui_color`. `_patch_config()` is the shared read-modify-write helper (`:309-323`).

### 3.3 `memory/long_term.json` (`memory/memory_manager.py`)

```
identity | preferences | projects | relationships | wishes | notes  → { key: entry }
sessions                                                           → [ {date, summary, language?} ]
entry = { value, updated "YYYY-MM-DD", category, source, confidence,
          created_at, updated_at, last_used_at, expires_at }
```

- `MAX_VALUE_LENGTH = 380` truncates values with `…` (`:18,130-133`). `_recursive_update` accepts nested dicts or scalars, skips empty/null values, drops entries with `confidence < 0.7`, and stamps `updated`/`updated_at` (`:136-165`).
- Two budgets, deliberately separate (`:20-45`): `MEMORY_MAX_CHARS = 200_000` is a runaway guard only; `PROMPT_CORE_CHARS = 900` and `PROMPT_INDEX_CHARS = 420` bound what actually enters each session prompt. `_trim_to_limit` deletes the oldest entries by `updated` until the guard is satisfied and reports the loss through a registered notifier so the UI can say what was forgotten (`:96-116`; registered at `main.py:2470`).
- `format_memory_for_prompt` sends identity in full, the most recent entries of every other category capped at `PROMPT_MAX_PER_CATEGORY = 6` within the core budget, then an interleaved **index of keys only** for the rest so `recall_memory` has something to look up (`:189-333`).
- `search_memory(query, limit=8)` is lexical, offline and sub-millisecond — key match 10, key substring 6, value substring 3, category 1 (`:338-389`). `all_entries_for_ui()` backs the memory panel, newest first (`:392-411`). `remember()`/`forget()` work on the six categories (`:413-432`).
- Session summaries: `save_session_summary()` keeps only the last `_SESSION_MAX = 3` entries with a 280-char summary (`:440-463`); `pop_last_session()` returns **and removes** the newest entry so a briefing cannot repeat it (`:466-488`).

### 3.4 `memory/projects.json` (`memory/project_index.py`)

Local machine paths and aliases, kept out of prompt memory (git-ignored). Keyed by resolved path as `{name, path, aliases, last_seen, **metadata}`, written through a `.tmp` replace (`:9-19`). `resolve_project(name)` matches name/aliases case-insensitively; on no match it looks for an exact folder name under `~/Desktop`, `~/Documents` and `cwd.parent`, requires a unique hit, else raises `Project not found or ambiguous; supply its exact path.` (`:22-32`).

### 3.5 `memory/profile_bootstrap.py`

Explicit one-shot private profile import, never scraped from plans or conversations. Accepts a dict limited to `identity, preferences, projects, device, notes`, ≤100 KB, scalar values only (`:14-29`), and refuses any key matching the sensitive-field pattern (password / secret / token / api key / credential / bank / wallet / phone / address / national id / medical) pointing at a separate private-memory policy (`:11,26-27`). Facts are written via `update_memory()` with `source='user_profile_import'`, `confidence=1.0` (`:30-33`), and a copy is persisted to `memory/profile.json` (git-ignored) as `{imported_at, facts}` (`:34-36`).

---

## 4. Dashboard server (`dashboard/server.py`)

Optional: without `fastapi`/`uvicorn` the server declares itself disabled (`server.py:21-28`, `856-860`). Constants: `PORT = 8000`, HTTPS alias `PORT + 1`, `MAX_UPLOAD_MB = 500` (`:40-41`).

### 4.1 Routes

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/static/crypto.js` | none | cached CryptoJS, else CDN redirect (`:546-552`) |
| GET | `/login` | none | `login.html` (`:554-556`) |
| GET | `/` | none (client-side token) | `app.html` with `__IP__`/`__PORT__` substituted; browser navigations cannot send headers (`:558-566`) |
| POST | `/login` | one-time PIN | consumes a pending 6-char key, issues bearer token + session key (`:568-587`) |
| GET | `/auto-login?key=` | one-time key in URL | QR target: token + device token, HTML stores them and redirects (`:589-634`) |
| POST | `/api/device-login` | device token | fresh bearer token for a previously paired device (`:636-656`) |
| POST | `/api/revoke-devices` | bearer | clears the device-token map only (`:658-665`) |
| POST | `/api/command` | bearer | accepts `{enc}` (AES) or `{text}` (plain), queues it (`:667-684`) |
| POST | `/api/wake` | bearer | invokes the wake callback (`:686-692`) |
| WS | `/ws/phone-audio?token=` | token in query | phone PCM frames into a bounded queue (`:696-720`) |
| POST | `/api/upload` | bearer | streams multipart to the uploads dir, 500 MB cap; 503 stub without `python-multipart` (`:729-780`) |
| GET | `/api/files` | bearer | name/size listing (`:782-796`) |
| GET | `/uploads/{filename}?token=` | token in query | serves a stored file (`:798-808`) |
| WS | `/ws?token=` | token in query | replays the last 50 history entries; accepts `{type:'command', enc\|text}` (`:810-836`) |

FastAPI docs endpoints are disabled (`docs_url=None, redoc_url=None`, `:539`).

### 4.2 Auth model

- **One-time PIN** — `new_key(expiry_secs=600)` (`:478-483`) generates 6 characters from an alphabet omitting `O I L 0 1` (`:69-70`); pending keys are pruned on each call and live in memory only. The desktop overlay requests them through `main._make_remote_key()` (`main.py:883-894`) and encodes `url + '/auto-login?key=' + key` into the QR (`ui.py:2741-2789`).
- **Bearer tokens** — `secrets.token_urlsafe(32)` added to `self._tokens`; `_auth()` is a plain membership check against `Authorization: Bearer …` (`:541-543`). Tokens have **no TTL and no removal path**, including `revoke-devices`.
- **Session key → AES key** — the PIN doubles as the session key; the server caches `SHA-256(session_key ‖ 'JARVIS-DASHBOARD-v1')` (`:73-78`, `:500-503`) and decrypts `base64(IV[16] ‖ ciphertext)` with AES-256-CBC + PKCS7 (`:81-90`). `_token_keys` maps token → session key (`:461,576-578`).
- **Device tokens** — `auto-login` issues a 32-byte device token stored in the phone's `localStorage` (`:630`); `/api/device-login` later mints new bearer tokens from it and returns the session key in the clear (`:646-656`). The map is in-memory, so a restart invalidates stored device tokens and the client falls back to the PIN form (`login.html:159-180`).
- **Command confidentiality is optional** — `/api/command` only decrypts when `enc` is present and otherwise accepts `text` (`:674-679`); the WebSocket behaves the same (`:826-829`).

### 4.3 TLS and certificate generation

`_ensure_certs()` (`:363-447`) runs once at startup and writes `config/certs/jarvis.key` + `jarvis.crt`: RSA-2048 self-signed, `CN=JARVIS Dashboard`, SANs `localhost`, `127.0.0.1` and the detected LAN address, valid 1 day back / 3650 days forward — deliberately not shipped in the repo so every install gets its own pair (`:366-374,396-428`). The private key is written **unencrypted** and `chmod 600` is best-effort, "largely a no-op on Windows" (`:430-441`). If `cryptography` is missing or generation fails, the function returns `False` and everything runs on plain HTTP, with the QR encoding `http://` instead (`:369-375,390-392,445-447`). `serve()` starts uvicorn on `0.0.0.0:8000` with TLS when a pair exists, plus an HTTPS alias on `PORT + 1` for manual browser entry (`:842-854,869-884`). `_local_ip()` picks the LAN address by UDP route probe to three well-known IPs, then hostname resolution, then interface enumeration (`:328-360`).

### 4.4 Uploads

Directory chosen at import time from `~/Downloads/JARVIS Uploads`, `~/Documents/JARVIS Uploads`, or `BASE_DIR/uploads` (`:44-59`). `_safe_filename()` applies `Path(raw).name` and strips `<>:"/\|?*`, control characters and leading/trailing dots/spaces, falling back to `upload` (`:724-727`); collisions get `_1`, `_2` suffixes (`:737-741`). Streaming enforces the 500 MB cap and deletes the partial file on overflow or error (`:743-765`); receipt is broadcast as `{type:'file_received'}` (`:767-772`). `/uploads/{filename}` strips separators again before joining (`:804`) and serves through `FileResponse`.

### 4.5 Broadcast, command queue, phone audio

`broadcast()` appends to `_history` (last 300) and fans out, dropping failed sockets (`:524-534`); `/ws` replays `_history[-50:]` to each new client (`:817-822`). Commands go to an unbounded `asyncio.Queue` consumed by `main._process_dashboard_commands()`, which waits up to 8 s for a live session, wakes Zaya if asleep and forwards the text as an owner turn (`main.py:2424-2450`). Phone audio uses `asyncio.Queue(maxsize=200)` and drops frames rather than blocking (`:470,710-714`); `main._relay_phone_audio()` moves them into the Gemini session, treats 1 s of silence as "phone mic inactive" and otherwise suppresses the PC microphone (`main.py:2398-2416`, gate at `main.py:1620`).

### 4.6 Firewall / network elevation (`_ensure_network_access`, `:99-308`)

Best-effort, run from an executor so startup never blocks (`:848,864`). **Windows**: checks the two rule names and whether any profile is `Public`, then builds a temporary `.bat` in `%TEMP%` that flips Public profiles to Private and adds `netsh advfirewall firewall add rule … protocol=TCP dir=in localport=<port> action=allow` plus a program rule for the current Python executable (`:142-175`). It first tries a direct run (works when elevated) and otherwise uses `ctypes.windll.shell32.ShellExecuteW(None, 'runas', bat_path, None, None, 0)` — a hidden-window elevated run behind the UAC prompt (`:198-231`). **macOS**: `socketfilterfw --add/--unblockapp` through an `osascript` admin dialog when the Application Firewall is on (`:234-260`). **Linux**: `ufw` → `firewalld` → `iptables` via `pkexec` or `sudo -n`, printing a manual command as fallback (`:262-307`).

### 4.7 Security posture and its limits

Provided: a session gate before any command, upload or socket; deliberate opt-in before the port is opened; upload path containment; FastAPI docs disabled; a separate loopback hook surface for WhatsApp.

Not provided, precisely:

- **The listener is LAN-wide.** `0.0.0.0` on `8000` and `8001` (`:850,877`), plus a firewall rule added **without `profile=`**, i.e. valid on Domain, Private *and* Public networks. The token is the only access control.
- **Tokens never expire and are never revoked.** `_tokens`/`_token_keys` have no TTL, cleanup or logout, and `revoke-devices` clears only `_device_sessions` (`:658-665`) — live bearer tokens survive that action until the process restarts.
- **Tokens travel in URLs** at `/ws?token=` (`:811`), `/ws/phone-audio?token=` (`:697`), `/uploads/{filename}?token=` (`:799`), and the QR login puts a one-time key in `/auto-login?key=` (`:589-593`), so they can persist in browser history and any logging along the path — in cleartext when TLS is off.
- **Persistent device credentials.** The device token lives in `localStorage` indefinitely, and `/api/device-login` hands back the **session key** (AES key material) to anyone presenting it (`:646-656`); read access to the phone's storage or any XSS in the served pages yields durable access plus the ability to forge encrypted payloads and read the replays.
- **Plain HTTP carries the gate itself.** Without `cryptography`, the PIN and the bearer token cross the LAN unencrypted, and the plaintext `text` command path (`:678-679,828`) is accepted even when TLS is active.
- **No throttling anywhere.** `/login` has no attempt limit or lockout; guessing is bounded only by the 600 s key lifetime and the 6-char space (31 symbols, `:69-70`).
- **No CSRF/origin checks** on the JSON, upload or WebSocket endpoints, no per-device audit, and the command queue feeding a privileged owner turn is unbounded (`:465`).
- **Elevated helper.** The firewall `.bat` is written into `%TEMP%` and then executed elevated while the UAC prompt hides its contents (`:172-175,204-211`), a user-writable file in the elevation path; it also silently demotes Public network profiles to Private (`:151-157`).

---

## 5. State file map

| Path | Written by | Contents | Git |
|---|---|---|---|
| `zayabar.json` | user / config dialog | companion settings (§1.4) | tracked |
| `zayabar.tmp` | config dialog (`services/zayabar.py:356-359`) | transient replace target | ignored (`.gitignore:66`) |
| `memory/zayabar_state.json` | `mouseReleaseEvent` (`zayabar.py:319-323`) | `{horizontal_position}` only | ignored (`.gitignore:65`) |
| `config/api_keys.json` | `memory/config_manager.py` | settings + Gemini keys (§3.2) | ignored (`.gitignore:9`) |
| `config/certs/jarvis.key`, `jarvis.crt` | `_ensure_certs` (`dashboard/server.py:363-447`) | self-signed TLS pair | ignored (`.gitignore:11`) |
| `config/hermes_bridge.json` | `HookReceiver.start/close` (`bridge.py:59-76`) | `{url, token}` hook sink; deleted on clean close | ignored (`.gitignore:72`) |
| `config/hermes_connection.json` | `_save_connection` (`pairing.py:71-95`) | pointer record (§2.2); no linked-device keys | ignored (`.gitignore:72`) |
| `config/hermes_pairing_qr.png` | pairing watcher (`pairing.py:105-110`) | QR while `waiting_scan`; deleted after pairing/cancel | ignored (`.gitignore:77`) |
| `config/jarvis.ico` | shipped | tray/executable icon | tracked |
| `memory/conversation.db` (+ `-wal`, `-shm`) | `ConversationStore` | owner chat + resume/operator state | ignored (`.gitignore:25,71`) |
| `memory/zaya_runtime.db` (+ `-wal`, `-shm`) | `WhatsAppStore` + `TaskRuntime` | `wa_*` tables (§2.4), `runtime_tasks`, `tool_results` | ignored |
| `memory/long_term.json` | `memory_manager` | prompt memory + session summaries | ignored (`.gitignore:24`) |
| `memory/projects.json`, `projects.tmp` | `project_index` | project aliases | ignored (`.gitignore:64,69`) |
| `memory/profile.json` | `profile_bootstrap` | record of an explicit profile import | ignored (`.gitignore:70`) |
| `memory/backups/` | local tooling | DB snapshots (e.g. pre-migration copies) | ignored (`.gitignore:68`) |
| `memory/water_state.json` | `plugins/water_reminder.py:22` | plugin hydration state | **untracked, not ignored** — same gap as `docs/codebase/plugins-tests-tooling.md:426` |
| `logs/runtime/events.jsonl` | `core/audit.write` (`core/audit.py:28-32`) | redacted audit events, append-only | ignored (`logs/`, `.gitignore:53`) |
| `logs/runtime/voice_status.json` | `main.py:1741`, read by `core/diagnostics.py:41` | latest voice-health marks | ignored |
| uploads dir | `/api/upload` | `~/Downloads/JARVIS Uploads` by default, else Documents, else `BASE_DIR/uploads` | outside the repo by default; the `uploads/` fallback is not ignored (`.gitignore` lists `downloads/`) |
| `%LOCALAPPDATA%\hermes` (or `$HERMES_HOME`, `~/.hermes`) | Hermes | `whatsapp/session/creds.json` (linked-device keys — never copied), `.env`, `gateway.pid`, `hooks/zaya-whatsapp/{handler.py,HOOK.yaml,zaya-path.json,zaya-hook-outbox.db}`, `hermes-agent/scripts/whatsapp-bridge/` | `.hermes/` ignored (`.gitignore:73`); `config/whatsapp_web/` ignored (`.gitignore:13`) |
| `assets/` | shipped | companion images and `assets/poke/*.wav` | tracked; `assets/zayabar/` ignored (`.gitignore:67`) |
| `dashboard/static/crypto-js.min.js` | `_ensure_crypto_js` (`server.py:310-323`) | cached CryptoJS; downloaded once if missing | tracked |

---

## 6. Observations and risks

**SQL and path handling — checks performed.**

- Every WhatsApp-store value is bound as `?`. The only interpolated SQL fragments are constant identifiers: `PRAGMA table_info({table})` / `ALTER TABLE` over a literal three-element list (`services/whatsapp/store.py:45-49`), the field-name list (`store.py:125-127`) and the `UPDATE {table} SET chat_id=?` loop over a constant tuple (`store.py:76-77`). No user string is concatenated into SQL.
- `WhatsAppStore.rows(query, values)` executes caller-supplied SQL text (`store.py:92-94`). Every call site in `services/whatsapp/` passes a literal, so it is safe today — but it is a raw escape hatch that a future caller could misuse with tool input.
- Inbox search binds `'%' + query[:200] + '%'` without escaping wildcards (`services/whatsapp/service.py:142`), unlike conversation search which escapes `%`, `_`, `\` (`memory/conversation_store.py:107`) — pattern injection (`%` matches everything), not SQL injection.
- Uploads/downloads: `Path(raw).name` + regex strip on write (`dashboard/server.py:724-727`), separator removal on read (`:804`), and `exists()`/`is_file()` required before serving — traversal is not reachable. Residual Windows gaps: reserved device names (`CON`, `NUL`), NTFS alternate data streams (`name:stream`), no length limits.
- Asset paths honour absolute paths (`core/zayabar_config.py:77-81`), so a locally edited `zayabar.json` can point the bar at any file on disk. Not remote-reachable.
- Outbound WhatsApp safety: JID validated before any transport call (`hermes_adapter.py:42`, `models.py:9-12`), owner text never routed through `cmd.exe` (`hermes_adapter.py:28-36`), hook flush refuses non-loopback URLs (`hook_handler.py:32`).

**Token lifetime and URL exposure.**

- Bearer tokens are minted at `server.py:575-577`, `:605-611`, `:647-650` and only ever added to `_tokens`; there is no expiry, rotation, logout or removal, and `revoke-devices` does not touch them (`:658-665`). `_aes_cache` accumulates one entry per session key (`:500-503`).
- Tokens appear in query strings at `:697`, `:799`, `:811`; the QR URL carries the one-time key (`:589-593`). Any log, screenshot, browser sync or shared browser profile can preserve them. Because `/api/device-login` returns `key` (`:656`) and the device token is durable (`:630`), one copy of the phone's storage yields lasting access to the owner command channel **including the AES key material** meant to protect command contents.

**Plain-HTTP fallback.**

- Certificate failure degrades silently to HTTP (`:390-392`, `:445-447`) and `serve()` then runs without SSL (`:869-884`). In that mode the 6-char PIN, bearer tokens and the unencrypted `text` payload cross the LAN in the clear. The comment at `:369-375` documents the fallback as intentional, so the encryption layer is a convenience, not a guarantee.

**Firewall elevation.**

- `netsh` rules are added without `profile=`, so the port stays open on Public networks (`:158-169`); the script also demotes Public profiles to Private (`:151-157`), weakening per-network posture without asking. The elevated helper is a `.bat` in `%TEMP%` (`:172-175`) launched with `runas` and `SW_HIDE` (`:204-211`): the user approves a UAC prompt whose contents are invisible, over a file other local processes could touch first. Hardening would be a read-only helper or printing the command instead of elevating. The same routine runs for the alias port (`:848`), so a first run can raise two UAC prompts.

**Unbounded growth.**

- `wa_messages`, `wa_alerts` and `wa_send_intents` have no retention or vacuum (`store.py:22-44`); `conversation.db.messages` is never pruned either — only readers are bounded (`recent` 32 000 chars, `search` 12 rows). Both databases grow without limit over months.
- Dashboard `_tokens`, `_token_keys`, `_aes_cache`, `_device_sessions` (`server.py:460-469`) are never pruned, while `_history` is capped at 300 (`:526-527`) and `_pending_keys` only inside `new_key()` (`:480`). `ReplyWorker._locks` keeps one `threading.Lock` per distinct chat forever (`handler.py:17,39-40`).
- `logs/runtime/events.jsonl` is append-only with no rotation or size cap (`core/audit.py:28-32`); by contrast the Hermes hook outbox is bounded to 7 days (`hook_handler.py:26`).

**Threading and lifecycle.**

- `WhatsAppStore` shares one `sqlite3.connect(..., check_same_thread=False)` behind an `RLock` with WAL and `busy_timeout=5000` (`store.py:17-21`); mutations run inside `with self.lock, self.db`, but a few call sites reach past the API and duplicate SQL under the same lock (`core/proactive_manager.py:17-19,38-40,58-68`, `actions/whatsapp.py:34-36`), spreading schema knowledge across modules.
- `ReplyWorker` is bounded (`max_workers=2` + `BoundedSemaphore(50)`) and serialises per chat, but load shedding is silent apart from one `system.warning` (`handler.py:15-24`). `service._supervise` retries `connect_live()` every 10 s under the same `RLock` used by `start()`/`close()` (`service.py:41-70`); `close()` joins the supervisor before tearing down bridge, worker and receiver (`72-83`).
- `AttachedProcess.kill()` can terminate an attached bridge on shutdown (`native_bridge.py:31-32`, `216-217`); the parent-timestamp check at `:51-56` is what keeps a bridge owned by another live process out of reach — if that heuristic misreads a given launcher, an unrelated bridge could be killed.
- Qt side: the bar publishes/subscribes on the shared bus and relies on queued signal delivery to keep widget work on the GUI thread (`zayabar.py:48`); `shutdown()` unsubscribes (`372-387`). `avatar.reaction.playing` has no publisher in this repository, so that branch cannot currently fire.
