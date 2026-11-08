# Zaya Mobile — Expanded PC & Zaya Capabilities

This document records the full suite of PC functions and Zaya primitives integrated natively into the Zaya Android companion application.

In accordance with core requirements:
- **Zero UI Changes:** Zaya's native Android user interface (animated avatar face, HUD visual states, chat streams, floating bubbles, quick chips) remains 100% preserved.
- **Zero Regressions:** All existing features (flashlight, app launcher, settings navigation, cellular telephony, notification listener/replies, media playback, screen capture/vision, multi-step tasks, memory engine) remain intact.
- **Zero Monetization:** Personal assistant — no billing, ads, subscriptions, or telemetry paywalls.

---

## 1. Ported Capabilities Matrix

| Function | Action ID | Origin | Risk Level | Confirmation Required | Execution Target | Description |
|---|---|---|---|---|---|---|
| **Math & Calculator** | `evaluate_math` | PC `terminal_exec` & Zaya Math Tool | `LOW` | No | On-Device | Safe arithmetic, trigonometry, percentages, square roots, and expression evaluation without internet requirements. |
| **Device Diagnostics** | `get_device_diagnostics` | PC `system_monitor` & Zaya Hardware | `LOW` | No | On-Device | Hardware health monitor: battery capacity, temperature, charging status, RAM used/free, internal storage, network type, and system uptime. |
| **Web Search & Knowledge** | `web_search` | PC `web_search` & Zaya Web Search | `LOW` | No | On-Device / Browser | Queries external knowledge with instant synthesis or default browser launching. |
| **Weather Report** | `get_weather` | PC `weather_report` & Zaya Weather | `LOW` | No | On-Device | Live weather conditions, temperature, humidity, wind speed, and forecast with resilient offline fallback. |
| **Daily Briefing** | `get_daily_briefing` | PC `doc_generator` & Zaya Morning Briefing | `LOW` | No | On-Device | Comprehensive executive morning/daily digest synthesizing date/time, battery, weather, active task status, and unread notifications. |
| **Countdown Timer** | `set_timer` | PC `reminder` & Zaya Scheduled Monitors | `LOW` | No | Android OS (`AlarmClock`) | Starts countdown timer via Android's native timer service. |
| **Alarm Clock** | `set_alarm` | PC `reminder` & Zaya Alarms | `MEDIUM` | No | Android OS (`AlarmClock`) | Sets scheduled wake-up or reminder alarm with custom label. |
| **Clipboard Read** | `get_clipboard` | PC `computer_control` & Zaya Clipboard | `LOW` | No | On-Device (`ClipboardManager`) | Inspects current system clipboard text. |
| **Clipboard Copy** | `set_clipboard` | PC `computer_control` & Zaya Clipboard | `LOW` | No | On-Device (`ClipboardManager`) | Copies generated or provided text into device clipboard. |
| **WhatsApp Direct Messaging** | `send_whatsapp_message` | PC `whatsapp` & Zaya Messaging | `HIGH` | **Yes** | Android OS (WhatsApp Intent) | Direct deep-link messaging to phone number or contact via WhatsApp with explicit confirmation gate. |
| **Storage & File Inspector** | `inspect_storage` | PC `file_controller` & Zaya File I/O | `LOW` | No | On-Device (`StatFs` / Storage) | Inspects device disk space and lists files in Downloads or Documents directory safely. |
| **Audio Stream Volume** | `set_volume` | PC `media_controller` & Hardware Specs | `LOW` | No | On-Device (`AudioManager`) | Sets volume level (0–100%) for media, ringtone, or alarm audio streams. |
| **Ringer Mode** | `set_ringer_mode` | PC `computer_settings` & Mobile Specs | `LOW` | No | On-Device (`AudioManager`) | Toggles phone ringer mode between `normal`, `vibrate`, and `silent`. |
| **PC Command Bridge** | `execute_pc_command` | PC `mobile_telekinesis` | `HIGH` | **Yes** | PC Companion WebSocket | Relays remote control actions (lock PC, media, sleep, screenshot, diagnostics) to connected laptop runtime. |
| **FX Currency Converter** | `convert_currency` | Zaya `fx_macro.py` | `LOW` | No | On-Device | Converts monetary amounts between global currencies (USD, EUR, GBP, JPY, CAD, AUD, INR, NPR, CNY, CHF, SGD) using standard exchange rates. |
| **File Reader** | `read_file` | Zaya `file_read.py` | `LOW` | No | On-Device | Safely reads lines from a local text or log file with path-traversal safeguards. |
| **File Writer** | `write_file` | Zaya `file_write.py` | `MEDIUM` | **Yes** | On-Device | Writes or appends text content to local notes/files with explicit user confirmation gate. |
| **Think Scratchpad** | `think` | Zaya `think.py` | `LOW` | No | On-Device | Internal reasoning scratchpad allowing the agent to formulate hypotheses or plan before executing without speaking aloud. |
| **Knowledge Lookup** | `lookup_knowledge` | Zaya `knowledge_tools.py` | `LOW` | No | On-Device | Queries structured knowledge facts and relational entities from local device memory. |

---

## 2. Architecture & Implementation Details

### `SystemUtilitiesController.kt`
Located at `mobile/android/app/src/main/java/com/zaya/companion/service/SystemUtilitiesController.kt`.
- Houses the self-contained mathematical parser supporting unary signs, parentheses, precedence (`*`, `/`, `%` over `+`, `-`), exponents (`^`), and trigonometric functions.
- Provides Zaya FX macro currency conversion between major international currencies.
- Safely reads and writes local text files with path traversal sanitization and size bounds.
- Provides reasoning scratchpad logging (`think`) and entity relational lookup (`lookup_knowledge`).
- Inspects system hardware using Android's native `BatteryManager`, `ActivityManager`, `StatFs`, `ConnectivityManager`, and `SystemClock`.
- Integrates with standard Android intents:
  - `AlarmClock.ACTION_SET_TIMER`
  - `AlarmClock.ACTION_SET_ALARM`
  - `Intent.ACTION_VIEW` for WhatsApp (`https://api.whatsapp.com/send`) and Web Search.

### Action Model & Registry
- `ActionModel.kt`: Each capability is represented as a typed data class extending `AndroidAction` with explicit `ActionRisk` classifications.
- `ActionRegistry.kt`: Discovers and reports all 29 capabilities (10 core + 19 expanded) to Gemini AI and local task planners.
- `ActionExecutor.kt`: Centrally executes each action with coroutine dispatch, cancellation checkpoints, and idempotency deduplication (`ConsequentialActionDeduplicator`).

### Confirmation & Security Safeguards
1. **Consequential Gates:** Actions that initiate external communications (`send_whatsapp_message`, `compose_sms`, `initiate_call`), alter local files (`write_file`), or execute remote desktop changes (`execute_pc_command`) return `ActionResultStatus.NEEDS_CONFIRMATION` unless explicitly confirmed by the user.
2. **Duplicate Suppression:** A 10-second sliding deduplication window prevents accidental double-execution from voice echoes, UI retries, or replayed events.
3. **No Private Leakage:** All diagnostic logs and local storage paths respect Android security boundaries and exclude private databases or tokens.

---

## 3. Verification & Testing

The expanded capabilities are verified through automated test suites:
- `tests/test_mobile_expanded_functions.py` (15 unit tests covering math AST, division-by-zero handling, scientific functions, wire protocol envelopes, confirmation gates, parameter validation, volume clamping, briefing generation, FX currency rates, file path traversal sanitization, and think scratchpad).
- Complete regression suite (62 tests passing):
  - `test_privacy_security_hardening.py`
  - `test_multi_step_task_engine.py`
  - `test_mobile_companion_iris.py`
  - `test_phone_call_flow.py`
  - `test_mobile_expanded_functions.py`
