# Extended action and plugin fixes — 21 October 2026

The IDs below refer to the owner's extended audit. Existing unrelated local
changes were preserved. All automated checks used fake providers/processes,
temporary files, or an offscreen Qt application; no real keys, messages,
applications, tunnels, or network requests were triggered.

| ID | Resolution |
| --- | --- |
| E19 | Deep research finds the result ancestor by class and reads actual destination hrefs, including decoded DuckDuckGo redirects. It no longer treats display breadcrumbs as a URL. |
| E20 | Screen takeover checks cancellation after generation, before each message, and immediately before paste/send. If generation is still finishing after stop, the result says stopping rather than claiming the worker has exited. |
| E21 | Takeover captures the destination identity before capturing/analyzing the screenshot, rejects missing identities, and checks that same destination before sending. Focus changes cannot bind the first reply to another window. |
| E22 | Calendar events are explicitly local-only. No fabricated Google Meet code is generated; the description and result explain Google Calendar/Meet are not connected. Existing saved real links are preserved. |
| E23 | Calendar deletion requires a nonempty exact ID or exact title. Duplicate titles require an ID; substrings no longer delete multiple events. |
| E24 | Calendar mutations check persistence and report failure if not saved. Writes use a same-directory temporary file and atomic replacement; a lock serializes read/change/write. Unreadable existing stores are not overwritten. |
| E25 | Tunnels require a reported URL and a live subprocess. Both output streams are drained. Failed startup is terminated and not retained; stale entries are not considered active. Explicit providers are honored and ports validated. Shutdown cleanup is exposed and registered for normal process exit. A reported public URL is not described as independently reachability-tested. |
| E26 | Ghost overlay now creates a real PyQt6 command window with text entry and Send. The GUI thread installs it with the owner-input callback; worker requests use queued signals and bounded acknowledgements. Tool status reflects actual widget visibility; missing initialization or acknowledgement is failure. |
| E27 | Web customization snapshots sessions from the actual browser registry under its lock and prefers the active browser. It retains honest partial/failure reporting. |
| E28 | Entire hotkey chords are validated before injection; unknown components reject the request. SendInput failures are reported and pressed modifiers are released. |
| E29 | Text uses properly declared SendInput/KEYBDINPUT with UTF-16 code units, including surrogate pairs, and validates the number of inserted input events. No physical typing was performed in validation. |
| E30 | Display append passes through the shared bounded rendering path. UI rendering and thread-safe clear/close acknowledgement are integrated separately in ui.py; no worker directly hides a Qt widget. The real UI must accept the full bounded payload, including its truncation notice. |
| E31 | OCR distinguishes extracted text from successful clipboard copying. An unavailable/failing clipboard returns partial with `copied_to_clipboard=false`; the extracted text remains available. |
| E32 | Both document generation and the Excel plugin sanitize worksheet reserved characters and handle an empty resulting name. |
| E33 | PDF titles, headings and body text are XML-escaped before ReportLab parsing, preserving literal requested text. |
| E34 | Generated documents and Excel plugin outputs reserve unused filenames atomically with O_EXCL. Existing files are preserved, including repeated same-minute requests; failed writes clean up only their newly reserved output. |

## Verification

- `python -m unittest tests.test_extended_action_fixes -q`: 20 checks passed.
- `python -m unittest tests.test_bug_sweep_regressions -q`: 32 checks passed.
- Scoped syntax/undefined-name Ruff checks and diff whitespace checks passed.

The focused checks include an actual offscreen Qt show/hide/submit cycle,
real XLSX/PDF writes inside temporary directories, destination switching,
cancellation during generation, failed calendar persistence, dead subprocesses,
and preserving existing output contents. Physical input, authenticated Google
Calendar, real message delivery, and public tunnel reachability are not claimed.

Tests are temporary verification scaffolding. Their eventual removal follows
the owner's separate request after project-wide verification is complete.
