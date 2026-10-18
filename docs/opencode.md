# Hidden coding sessions

Zaya sends owner coding requests to the locally installed OpenCode CLI through a
hidden process. There is no console window to focus or type into. OpenCode uses
its existing provider, model, agent and permission settings; Zaya does not change
them. Install and sign in to OpenCode normally before using this feature.

Say which project to work in and what to change. Names are resolved under the
Desktop, Desktop/ZayaProjects, Documents and dev folders; an absolute path must
also be inside one of those roots. The directory must already contain project
files. If several projects share a name, give the absolute path.

Zaya reports reading, finding an issue, editing and checking from actual JSON
events in first-person speech. She remains available for other conversation.
"How is the coding going?" reads the stored state and response. "Continue" with
a follow-up sends another prompt to that exact session. "Stop coding" terminates
the process tree; closing Zaya also stops it and leaves a resumable local record.
No coding work resumes automatically on app startup.

OpenCode permission refusals or requests for more information are returned for
Zaya to explain. Zaya never silently adds `--auto`. A response arriving is not
independent proof that a fix works; the response and recorded checks must support
any stronger claim. Raw terminal output and model prose are not read aloud as
instructions, and external contacts cannot start, resume, stop or inspect jobs.

Local state is saved in ignored `memory/coding_jobs.json`; it includes bounded
responses and session identifiers. The runtime task store records the active
child task separately from the tool call that started it.

Offline verification:

    .venv\Scripts\python.exe -m unittest tests.test_coding_jobs tests.test_coding_voice tests.test_opencode_events

A real CLI smoke check is opt-in and uses temporary project files. It sends two
small prompts through the configured OpenCode provider:

    $env:ZAYA_OPENCODE_SMOKE = '1'
    .venv\Scripts\python.exe -m unittest tests.test_coding_jobs.RealOpenCodeSmoke

This does not verify a physical microphone or speakers. Live narration uses the
same existing voice provider and owner interruption gates as other notices.
