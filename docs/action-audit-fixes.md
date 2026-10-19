# Action findings from the consolidated audit

This records the disposition of action-module entries in the owner's pasted
audit. Claims were checked against the current source before changes. Numbers
refer to that audit; duplicate numbers describe one fix. WhatsApp action #87
is covered by the separate WhatsApp work.

| Findings | Disposition |
| --- | --- |
| #1, #8 | Already fixed: dev_agent shared key lookup and quoted argument splitting. |
| #18 | Already fixed: browser logs use a ToolResult summary when applicable. |
| #23 | Fixed: Windows executable launches use an argument list without a shell; protocol launches use Windows ShellExecute via os.startfile, not a constructed `start` command. |
| #24 | Fixed: PowerShell title is single-quoted with apostrophes escaped; AppleScript receives the title as an argument. Linux already passed arguments without shell interpolation. |
| #25 | Fixed: generated desktop code now goes through the real owner confirmation gate, showing the code for review. The convenience namespace is explicitly not considered a sandbox. Owner Full Access retains its existing behavior. |
| #26, #66 | Not an injection defect: schtasks is invoked with an argument list without a shell; the quoted values are Python's executable and the module's actual filesystem path, not supplied text. Windows paths cannot contain double quotes. Existing task registration behavior is retained. |
| #27, #91 | No model-input injection was present, but brittle nested shell parsing was removed. Linux brightness reads xrandr output in Python and adjusts the selected output using arguments and a bounded brightness value. |
| #32 | Fixed: archived message excerpts retain their beginning within the existing five-message and character budgets. |
| #49, #53, #55, #56, #59, #61, #76 | Fixed latent helpers: all use the shared Gemini key pool, including plural-only configuration. Most were unused helpers; the active computer_control screen key lookup was also corrected. |
| #50 | Fixed: unknown text-processing actions retain the original requested instruction when constructing the custom prompt. |
| #51 | Fixed: Python file processing uses the current interpreter, preserving the application's installed environment. |
| #52, #54 | Fixed: audio and wallpaper temporary paths are reserved using NamedTemporaryFile rather than mktemp. Audio and downloaded temporary files are cleaned up in finally blocks. A converted Windows wallpaper bitmap remains available to the operating system as before. |
| #57 | Fixed: removed the stale encoded flight itinerary; the requested airports/date and passenger settings are encoded into the search query. |
| #58 | Empty flight response was already caught and returned no flights; now None text is explicitly treated as empty before parsing. |
| #60 | Fixed: absent candidates/content/parts yield an empty result instead of IndexError/AttributeError in both grounded search and headline retrieval. |
| #62 | Fixed: a dialog-created Tk root is destroyed afterward; an existing application root remains untouched. The visible dialog title is Zaya. |
| #63 | Fixed: installed youtube-transcript-api 1.2.4 uses instance `.list()` and snippet objects. Both current and older transcript shapes are supported. |
| #64 | Fixed defensively: browser results are normalized before adding media evidence, preserving failure/partial status. |
| #65, #92 | Fixed: updating all Epic games opens the launcher once and does not launch up to ten games. The result accurately delegates updates to the launcher's settings. |
| #72 | Fixed: build repair decisions use the actual process exit code. Successful stderr output no longer triggers repair; nonzero exit with empty output does. |
| #83 | Deliberate owner tool scope, not a defect: the owner can manage files under their home directory. External-source trust checks remain required. |
| #84 | Fixed: largest-file scans retain only top results, cap files/time, avoid symlink traversal and explicitly label a partial scan. |
| #85 | Fixed: screen preferences use the shared locked atomic settings writer rather than overwriting the configuration independently. |
| #86 | Fixed: JPEG encoding failure raises a useful capture error instead of dereferencing a missing buffer. |
| #88 | Fixed: desktop organization records moved paths in the existing undo stack; undo does not overwrite files subsequently created at original paths. |
| #89 | The original allegation was not an established defect: Popen is asynchronous and spawning a long-running desktop launcher must not wait for its completion. Existing launch errors are caught. Actual send verification remains separate from process launch. |
| #90 | Return annotation corrected to `str | ToolResult`; the dispatcher already supports both result types. |

## Focused verification

Run `python -m unittest tests.test_action_command_safety tests.test_action_audit_regressions -q`
with the project environment. These cover hostile title/protocol text, shared
keys, custom document instructions, current interpreter selection, history
truncation, desktop approval and undo, process exit codes, flight search input,
empty search candidates, current transcript objects, atomic preference writes,
brightness bounds, and avoiding concurrent game launches.

No real applications are launched or external messages sent by these tests.
