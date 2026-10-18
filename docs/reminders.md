# Reminder delivery

Zaya stores each reminder in the private, ignored `memory/reminders.db` ledger.
Relative delays are measured when the tool is called; absolute dates and times
use the computer's local timezone. Same-time reminders have separate identifiers.

While Zaya is connected, due reminders enter the isolated voice notification
channel. Owner speech, mute and current responses retain priority. A reminder
can announce while wake-word mode is asleep without reopening the microphone.
A failed voice attempt stays pending and retries after 30 seconds. Overdue
reminders are identified as overdue after restart.

The OS scheduler also runs a hidden desktop callback. Windows uses its native
notification APIs through PowerShell rather than the broken legacy toast import.
A callback failure records an error and exits nonzero; the script remains for
retry. Windows tasks retry failures up to three times, a minute apart. A callback
that sees a cancelled or already submitted reminder does not notify it again.

`reminder action=status` reports due time, background registration, errors,
`desktop_notified_at` and `voice_queued_at`. These timestamps record submission
to the notification/audio systems, not proof of physical visibility or audibility.
Older scheduler-only reminders have no new delivery ledger; their notification
contents and old scheduled tasks are preserved.

If background registration fails, the result is explicitly partial. The saved
reminder can still be announced while Zaya is running. If Zaya is closed, desktop
fallback requires the normal operating-system login/session and scheduler.

Run offline delivery, persistence and failure tests:

    .venv\Scripts\python.exe -m unittest tests.test_reminders

The opt-in Windows scheduler test creates a uniquely named temporary task,
checks that the actual scheduler invokes its callback, and deletes the test task.
Its desktop notification is stubbed so automated checks do not show a popup:

    $env:ZAYA_REMINDER_SCHEDULER_SMOKE = '1'
    .venv\Scripts\python.exe -m unittest tests.test_reminders.RealReminderSchedulerTests
