# Consolidated bug review, 19 October 2026

The supplied list contains findings numbered 1–92, duplicate entries, already
fixed items and intentional policies. Each remaining area was checked against
the current implementation. Detailed numbered dispositions are in
[action-audit-fixes.md](action-audit-fixes.md),
[runtime-audit-fixes.md](runtime-audit-fixes.md) and
[phone-audit-fixes.md](phone-audit-fixes.md).

## Remaining core and WhatsApp findings

| Finding | Disposition |
| --- | --- |
| 38 | Fixed: malformed bridge send/health JSON is validated; an unverified send never automatically retries. |
| 39 | Not reproducible: reply context is capped at 60 rows, with a 16,000 character budget. Per-row text limits cannot become negative within that bound. |
| 40 | Fixed: owner device suffix normalization preserves the account number and does not invent a JID for a missing account ID. Invalid receipt payloads are skipped. |
| 41 | Fixed: malformed cached results return a failed, non-retryable recorded result. They cannot cause a previous side effect to execute again. |
| 82 | Fixed: a hook receiver can close before starting, without waiting forever in HTTP shutdown. |
| 87 | Fixed: WhatsApp tool handles network and SQLite failures as failed results, preserving owner/trust checks. |

## Already read or answered WhatsApp messages

Incoming messages now have a chat read watermark. Manual owner replies clear
only earlier incoming messages; later arrivals stay unread. Explicit successful
owner sends clear through send start, preserving messages received during
delivery. Existing recorded manual replies repair stale counts on startup.
Read state survives contact-alias merges. Read/replied messages and late
classification results cannot generate stale spoken alerts.

The owned Hermes bridge observes account read-state updates and bounded history
read metadata. This never sends read receipts or allows contact text to run
tools. Historical snapshots use their original chat timestamp, not the time
Zaya receives them. Read metadata is coalesced separately and cannot evict real
messages. The upstream bridge source and linked credentials remain intact; a
private instrumented copy resolves its existing dependencies. Unsupported
upstream versions retain ordinary messaging and expose unavailable read sync
in status. Existing unknown/live-owned bridge processes are never taken over.

The unread query includes only an unread incoming preview. The tool explicitly
routes requests for new messages to that query, instead of conversation history.
Ordinary auto replies, shared current activity and per-chat mode behavior remain.

## Verification limits

The full desktop suite completed 413 tests: 407 passed and six optional tests
were skipped. All 59 Android JVM tests passed. Scoped Ruff syntax/undefined-name
checks and the instrumented installed Hermes bridge's Node syntax check passed.
Tests do not send real WhatsApp messages or open the owner's camera.
Physical phone call quality and linked-account
read events still need normal device use to confirm end to end. The list's
“untested” inventory was not itself evidence of additional defects.
