# Behavior and provider repairs — 21 October 2026

These repairs accompany the extended action, runtime and phone repair notes.
The notes describe the supplied audit findings; they do not claim that every
possible application or device bug has been eliminated.

- A missing request scope creates a fresh identity rather than the literal
  `None`. Fragments of one spoken request share its scope. The complete owner
  instruction reaches coding tools rather than losing everything after 300
  characters. Fresh startup does not reuse an old owner goal or inject the
  previous session summary into the live provider.
- Normal-launch playback receives its audio helpers explicitly. Echo protection
  records output before optional animation; an animation error cannot silently
  disable echo bookkeeping. Isolated lifecycle and conversation checks passed.
- Project opening resolves Desktop against the real Desktop directory and
  launches a verified VS Code executable with an absolute folder. The result
  distinguishes a launch request from proof of the opened workspace, and keeps
  the real confirmation callback tied to its originating task.
- Requested document deliveries receive independent artifact checks after coder
  review. Actual Office/PDF readers reject placeholder containers. Input formats
  and topic names do not become deliverables; explicit owner corrections replace
  earlier format choices. HTML cannot satisfy a requested PowerPoint file.
- E39: OpenAI-compatible streamed tool fragments are assembled into complete
  calls. Gemini and Ollama streaming also preserve structured tool calls.
  Invalid tool arguments fail explicitly; interrupted HTTP streams use typed
  provider failures and close their responses.
- E40: Provider fallback is allowed before semantic output begins. Once text or
  a tool call has been emitted, interruption is reported rather than appending
  another provider's unrelated response.
- The Qt thread owns real overlay and display operations. Display delivery,
  clear and close have bounded acknowledgements, and the service's full bounded
  content reaches the UI. Shutdown closes owned coding jobs and tunnels.
- Remote reconnect queries status without replaying commands. Neither the first
  tool result nor an unrelated spoken turn declares a whole remote goal complete.
  Without reliable whole-goal correlation the phone retains acknowledgement;
  it must not display invented completion.
- A final transport check also found hardware status wrapped in an unread
  payload. Its fields now reach the real event cache. Phone awareness starts
  with unknown hardware rather than a fabricated full battery, labels cached
  readings as last reported, and counts WhatsApp records rather than metadata
  keys. Unavailable WhatsApp state is not described as synced. An isolated
  transport/cache check passed without touching a device or owner data.

## Verification boundaries

The final combined Python run completed 593 checks: 587 passed and six skipped
(122.680 seconds). Source compilation and scoped undefined-name checks passed.
The 98 Python source/fixture files and 14 Android test sources were then removed
at the owner's request. Android's 100 JVM checks passed with zero failures;
release lint reported zero errors and the signed release build passed.
Earlier fixture assumptions about fabricated Meet links, simulated offline
success, model-controlled approval and unconfirmed SMS delivery were corrected
before that run, rather than restoring those incorrect product behaviors.

Validation used isolated browsers, temporary files/databases, fake providers and
phone transports, and offscreen Qt windows. Android JVM checks and local builds
were run. Physical microphone/echo conditions, phone foreground-service and
permission transitions, cellular calls, SMS, screen capture and real contact
delivery require checks after restarting the updated applications.

The owner requested removal of project-owned test suites and fixtures after
verification. Dependencies and their bundled tests are not part of that removal.
Source compilation, undefined-name checks and Android lint/build remain in CI
and the release publisher. Earlier test references in documentation are
historical evidence rather than runnable instructions for the final tree.
