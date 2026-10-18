# Supervised coding sessions

Zaya handles coding requests as a coordinator. A short request such as "make a
simple calculator" becomes a concrete brief with basic behavior, error cases,
relevant checks and run instructions. Existing project conventions and explicit
owner constraints take precedence over defaults. The original owner request is
kept separately from the compiled prompt and is included once, not pasted twice.

Use `coding_job start` with the existing project directory and task. For a new
project, choose a folder name and set `create_project=true`; the directory is
created under Desktop/ZayaProjects without replacing existing files. Explicit
paths must be inside the configured project roots. Ambiguous existing names
require an exact path. A missing directory never requires an interactive terminal.

The owner talks to Zaya. She prompts the installed OpenCode CLI through a hidden
process, reads its JSON events, and narrates meaningful progress. OpenCode retains
its existing provider, model, agent and permission settings; Zaya does not add
`--auto`, inject permission configuration or operate its interactive interface.
Direct OpenCode worker launches through `terminal_exec` are routed back to
`coding_job`; simple CLI help/version inspection is still available.

After every completed pass, Zaya's tool-free reviewer checks the response and
observed steps against the brief. Missing requirements or checks cause a focused
follow-up in the same saved OpenCode session. Follow-ups are constructed from
selected items in the original brief; the reviewer cannot turn quoted output
into an arbitrary new prompt. There are at most three OpenCode passes per owner
request. Permission/input blockers, unavailable review, or exhausted passes leave
the job waiting for the owner instead of silently retrying or claiming completion.

`status` reports planning, work, review, pass count, brief, responses and recorded
checks. `continue` can supply a new owner follow-up and retains the original
request. `stop` terminates the current process tree and prevents another pass.
Closing Zaya also stops work and leaves the session resumable. Nothing resumes
automatically on startup. A review is not an independent guarantee of correctness;
reported checks and available evidence determine what Zaya can claim.

Bounded job state is private in ignored `memory/coding_jobs.json`. The runtime
store tracks the coding task through execution and review. Speech uses local
first-person progress templates through the isolated voice channel. OpenCode
output is untrusted evidence and cannot authorize unrelated tools or actions.

Offline checks:

    .venv\Scripts\python.exe -m unittest tests.test_coding_jobs tests.test_coding_supervisor tests.test_coding_voice tests.test_opencode_events

Real CLI prompt/follow-up checks are opt-in:

    $env:ZAYA_OPENCODE_SMOKE = '1'
    .venv\Scripts\python.exe -m unittest tests.test_coding_jobs.RealOpenCodeSmoke

The real supervised calculator check invokes the brief planner, OpenCode and
reviewer using their existing configured providers, then runs independent
arithmetic and division-by-zero checks on the generated program:

    $env:ZAYA_OPENCODE_SUPERVISOR_SMOKE = '1'
    .venv\Scripts\python.exe -m unittest tests.test_coding_supervisor.RealSupervisedCodingTests

These tests use temporary projects and do not edit the owner's projects or
verify physical microphone/speaker behavior. Restart Zaya after updating the
application code so new requests use the supervised route.
