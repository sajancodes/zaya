# IRIS Hybrid Universal Assistant & Mobile-Desktop Synergy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Zaya into a high-performance, voice-first desktop & mobile assistant equipped with all 16 IRIS chapters, double-clap wake detection with persistence across PC restarts, a universal multi-provider LLM combiner (Gemini, OpenAI, 9Router, OpenRouter, Ollama), and mobile companion telekinesis without removing any existing features.

**Architecture:** A modular Python engine for PC and Android companion communication. Built on Zaya's existing `ActionRegistry`, `core/execution_policy.py`, and `mobile_protocol.py`, adding clean non-blocking acoustic event detection, a provider-agnostic router with automatic fallback, high-DPI desktop automation tools, and extended companion event contracts.

**Tech Stack:** Python 3.10+, NumPy (acoustic processing for clap detection), Win32 API / ctypes (global media keys, ghost typing, high-DPI cursor), Playwright / Requests, OpenRouter / 9Router / OpenAI / Gemini client abstraction, openpyxl, python-pptx, reportlab.

**Spec:** `documentation-features-to do/1.md`, `documentation-features-to do/artetctiture.md`, `documentation-features-to do/corefeaturespc.md`, `documentation-features-to do/corefeaturesphone.md`, `documentation-features-to do/idea.md`.

## Global Constraints
- Commit identity: `sajancodes <ab4290025@gmail.com>`. Verify before committing.
- Do not remove or break existing actions, tests, or companion pairing workflows.
- All operations must enforce owner security boundaries (`require_owner()` from `core/execution_policy.py`).
- Keep code fully typed, tested with standard `unittest`, and clean of unnecessary dependencies.
- No placeholders, TODOs, or mock-only stubs for primary workflows.

---

### Task 1: Double-Clap Acoustic Detection & Persistent Startup Engine

**Files:**
- Create: `core/double_clap.py`
- Create: `actions/double_clap_toggle.py`
- Create: `tools/clap_persistence.py`
- Create: `tests/test_double_clap.py`

**Interfaces:**
- Consumes: Raw int16 PCM audio chunks (16kHz), `config/api_keys.json`
- Produces: `DoubleClapDetector.feed(chunk) -> bool`, `on_double_clap` callback, `double_clap_toggle` action

- [ ] **Step 1: Write the failing tests for double-clap acoustic detection**
Test temporal separation (200-750ms), energy threshold ratio, ambient noise rejection, and toggle persistence.

- [ ] **Step 2: Run test to verify it fails**
Run: `.venv\Scripts\python.exe -m unittest tests/test_double_clap.py`

- [ ] **Step 3: Implement `core/double_clap.py`, `actions/double_clap_toggle.py`, and `tools/clap_persistence.py`**
Implement the fast dual-transient peak detector with zero-crossing and energy ratio checks, plus registry/startup auto-launch setup for Windows.

- [ ] **Step 4: Run tests and ensure they pass**
Run: `.venv\Scripts\python.exe -m unittest tests/test_double_clap.py`

- [ ] **Step 5: Commit Task 1**
Git commit: `feat: add double-clap detection engine and persistent startup toggle`

---

### Task 2: Universal Multi-Provider LLM Combiner & Router

**Files:**
- Create: `core/universal_router.py`
- Modify: `core/llm_client.py`
- Create: `tests/test_universal_router.py`

**Interfaces:**
- Consumes: `config/api_keys.json` provider definitions (gemini, openai, openrouter, 9router, ollama, custom base URLs)
- Produces: `UniversalLLMRouter.chat_complete()`, `UniversalLLMRouter.route_with_fallback()`, provider telemetry

- [ ] **Step 1: Write failing tests for universal router**
Test routing to Gemini, OpenAI, OpenRouter, 9Router, and automatic fallback when a provider returns 429 or network errors.

- [ ] **Step 2: Run tests to verify they fail**
Run: `.venv\Scripts\python.exe -m unittest tests/test_universal_router.py`

- [ ] **Step 3: Implement `core/universal_router.py` and hook into `core/llm_client.py`**
Build uniform request and response normalization, multi-key rotation, 9Router/OpenRouter header injection, and failover chaining.

- [ ] **Step 4: Run tests to verify they pass**
Run: `.venv\Scripts\python.exe -m unittest tests/test_universal_router.py`

- [ ] **Step 5: Commit Task 2**
Git commit: `feat: implement universal multi-provider LLM combiner with 9Router and failover`

---

### Task 3: ScreenPeeler AI OCR, Floating Mini Ghost Overlay, and Ghost Keyboard

**Files:**
- Create: `actions/screen_peeler.py`
- Create: `actions/ghost_keyboard.py`
- Create: `core/ghost_overlay.py`
- Create: `actions/ghost_overlay.py`
- Create: `tests/test_screen_peeler.py`
- Create: `tests/test_ghost_overlay.py`

**Interfaces:**
- Consumes: Screen coordinate captures, Windows Win32 keyboard/input events
- Produces: `screen_peeler` action, `ghost_keyboard` action, `ghost_overlay` action

- [ ] **Step 1: Write failing tests for ScreenPeeler and Ghost Overlay**
Test region coordinates capture parsing, OCR text extraction formatting, ghost keyboard string injection, and mini overlay dispatching.

- [ ] **Step 2: Run tests to verify they fail**
Run: `.venv\Scripts\python.exe -m unittest tests/test_screen_peeler.py tests/test_ghost_overlay.py`

- [ ] **Step 3: Implement `screen_peeler.py`, `ghost_keyboard.py`, `core/ghost_overlay.py`, and `actions/ghost_overlay.py`**
Full implementation using high-DPI coordinate scaling, clipboard population, and cursor-aligned overlay invocation.

- [ ] **Step 4: Run tests to verify they pass**
Run: `.venv\Scripts\python.exe -m unittest tests/test_screen_peeler.py tests/test_ghost_overlay.py`

- [ ] **Step 5: Commit Task 3**
Git commit: `feat: implement ScreenPeeler OCR, ghost keyboard typer, and ghost overlay`

---

### Task 4: Fast Local Code Search and Localhost Wormhole Tunnels

**Files:**
- Create: `actions/code_search.py`
- Create: `actions/port_tunnel.py`
- Create: `tests/test_code_search.py`
- Create: `tests/test_port_tunnel.py`

**Interfaces:**
- Consumes: Filesystem queries, local port numbers (e.g. 3000, 8000)
- Produces: `fast_code_search` action (file paths + line numbers), `deploy_wormhole` action (public tunnel URL)

- [ ] **Step 1: Write failing tests for fast code search and port tunneling**
Test pattern matching, line numbering, exclusion of ignored dirs, and tunnel lifecycle management (start/stop/status).

- [ ] **Step 2: Run tests to verify they fail**
Run: `.venv\Scripts\python.exe -m unittest tests/test_code_search.py tests/test_port_tunnel.py`

- [ ] **Step 3: Implement `actions/code_search.py` and `actions/port_tunnel.py`**
Fast native regex/file scanner without external heavy indexers; localtunnel/bore/cloudflared subprocess tunnel manager.

- [ ] **Step 4: Run tests to verify they pass**
Run: `.venv\Scripts\python.exe -m unittest tests/test_code_search.py tests/test_port_tunnel.py`

- [ ] **Step 5: Commit Task 4**
Git commit: `feat: add fast local code search and localhost wormhole tunneling`

---

### Task 5: Autonomous Deep Web Research and Real-Time Web Customization

**Files:**
- Create: `actions/deep_research.py`
- Create: `actions/web_customizer.py`
- Create: `tests/test_deep_research.py`
- Create: `tests/test_web_customizer.py`

**Interfaces:**
- Consumes: Research topics, URLs, CSS/JS injection payloads
- Produces: `deep_research` action (markdown report with citations), `web_customize` action (mutates active browser DOM/CSS)

- [ ] **Step 1: Write failing tests for deep research and web customization**
Test multi-step source crawling synthesis and CSS/JS script payload generation.

- [ ] **Step 2: Run tests to verify they fail**
Run: `.venv\Scripts\python.exe -m unittest tests/test_deep_research.py tests/test_web_customizer.py`

- [ ] **Step 3: Implement `actions/deep_research.py` and `actions/web_customizer.py`**
Recursive query decomposition, multi-source compilation, citation tracker, and browser DOM style injector.

- [ ] **Step 4: Run tests to verify they pass**
Run: `.venv\Scripts\python.exe -m unittest tests/test_deep_research.py tests/test_web_customizer.py`

- [ ] **Step 5: Commit Task 5**
Git commit: `feat: add autonomous deep web research and live web customization`

---

### Task 6: Document & Presentation Generation (PPT, Excel, PDF) & Widget Forge

**Files:**
- Create: `actions/doc_generator.py`
- Create: `actions/widget_forge.py`
- Create: `tests/test_doc_generator.py`
- Create: `tests/test_widget_forge.py`

**Interfaces:**
- Consumes: Topic/data for slides, tables for spreadsheets, widget specifications
- Produces: `generate_document` action (generates .pptx / .xlsx / .pdf), `widget_forge` action (creates live floating widgets)

- [ ] **Step 1: Write failing tests for document generator and widget forge**
Test slide deck creation, workbook generation, PDF formatting, and standalone HTML widget output.

- [ ] **Step 2: Run tests to verify they fail**
Run: `.venv\Scripts\python.exe -m unittest tests/test_doc_generator.py tests/test_widget_forge.py`

- [ ] **Step 3: Implement `actions/doc_generator.py` and `actions/widget_forge.py`**
Structured presentation builder, spreadsheet generator with styling, aesthetic PDF exporter, and widget renderer.

- [ ] **Step 4: Run tests to verify they pass**
Run: `.venv\Scripts\python.exe -m unittest tests/test_doc_generator.py tests/test_widget_forge.py`

- [ ] **Step 5: Commit Task 6**
Git commit: `feat: add generative PPT, Excel, PDF generator and live widget forge`

---

### Task 7: Global Desktop Media Controls & Interactive Google Calendar

**Files:**
- Create: `actions/media_controller.py`
- Create: `actions/calendar_scheduler.py`
- Create: `tests/test_media_controller.py`
- Create: `tests/test_calendar_scheduler.py`

**Interfaces:**
- Consumes: Spoken media actions ("pause", "next", "mute"), Calendar query/schedule payloads
- Produces: `control_media_playback` action, `calendar_schedule` action

- [ ] **Step 1: Write failing tests for media control and calendar scheduler**
Test keybd_event code mapping for Play/Pause/Next/Prev/Mute and 48-hour schedule validation.

- [ ] **Step 2: Run tests to verify they fail**
Run: `.venv\Scripts\python.exe -m unittest tests/test_media_controller.py tests/test_calendar_scheduler.py`

- [ ] **Step 3: Implement `actions/media_controller.py` and `actions/calendar_scheduler.py`**
Win32 keybd_event virtual key codes for system-wide media playback; full calendar event parser with Meet links and persistence.

- [ ] **Step 4: Run tests to verify they pass**
Run: `.venv\Scripts\python.exe -m unittest tests/test_media_controller.py tests/test_calendar_scheduler.py`

- [ ] **Step 5: Commit Task 7**
Git commit: `feat: add global Win32 media key controls and calendar scheduler`

---

### Task 8: Mobile Telekinesis, Android Companion IRIS-MX Protocols & Multi-Device Support

**Files:**
- Modify: `core/mobile_protocol.py`
- Modify: `dashboard/mobile_api.py`
- Create: `actions/mobile_telekinesis.py`
- Create: `tests/test_mobile_companion_iris.py`

**Interfaces:**
- Consumes: Android companion incoming call events, notifications, hardware commands
- Produces: Multi-device connection support (up to 2 devices), `control_incoming_call`, `manage_notification_listener`, `control_device_hardware`

- [ ] **Step 1: Write failing tests for extended mobile companion protocol**
Test incoming call event envelope, notification listener event, auto-reply payload, hardware toggle dispatch, and 2-device pairing limit.

- [ ] **Step 2: Run tests to verify they fail**
Run: `.venv\Scripts\python.exe -m unittest tests/test_mobile_companion_iris.py`

- [ ] **Step 3: Implement protocol extensions and `actions/mobile_telekinesis.py`**
Wire extended types into `core/mobile_protocol.py` and `dashboard/mobile_api.py`.

- [ ] **Step 4: Run tests to verify they pass**
Run: `.venv\Scripts\python.exe -m unittest tests/test_mobile_companion_iris.py`

- [ ] **Step 5: Commit Task 8**
Git commit: `feat: extend mobile companion protocol for IRIS-MX call, notification and hardware actions`

---

### Task 9: System Integration, Full Test Verification, and Push

**Files:**
- Modify: `main.py` / `core/action_loader.py` (if any wiring adjustments needed)
- Verify entire test suite: `unittest discover -s tests -t .`
- Push feature branch to remote.

- [ ] **Step 1: Run complete test suite across the repository**
- [ ] **Step 2: Verify git status, author identity, and clean diff**
- [ ] **Step 3: Push branch `feature/iris-hybrid-engine` to remote**
