# Phone startup and Zaya restart

Created and developed by Sajan Rai.

- Calling a closed Zaya from the Android app contacts the lightweight laptop
  launcher, waits for the existing paired connection and a live assistant
  session readiness signal, then sends one call request.
  The phone shows startup progress and allows cancellation. It never enables the
  phone microphone before an answered call.
- The laptop must be powered on, signed into Windows and reachable over
  Tailscale. Pair using the laptop's `*.ts.net` address. This does not power on
  or unlock the computer. The launcher uses TCP 8002; dashboard 8000 and its TLS
  alias 8001 retain their existing roles.
- `tools/phone_wake.py --install` installs the current user's `ZayaPhoneWake`
  logon entry and starts the hidden listener. Normal desktop startup also
  ensures it is installed. Closing Zaya leaves this small listener available;
  it does not keep Zaya's model, microphone, tools or WhatsApp connection alive.
- The listener accepts only loopback/Tailscale peers and validates the existing
  Android pairing credential against the revocation-aware device registry.
  Requests cannot select a command, executable, directory or prompt. Repeated
  requests share an already starting desktop; the desktop's single-instance
  lock is the final duplicate protection. Requests are bounded and rate limited;
  credentials and request bodies are not logged. Android refuses redirects and
  sends wake credentials only to the same paired Tailscale hostname.
- Say **Restart Zaya**, use **Controls → Restart Zaya**, or choose **Restart
  Zaya** in the companion/tray menu. A separate hidden helper waits for the
  exact old process to exit before starting the replacement. Repeated clicks
  do not schedule repeated restarts. If the old process fails to exit within
  60 seconds, the helper records failure rather than starting another assistant.
  Windows itself is not restarted.
- Desktop exit closes the already-started owned WhatsApp bridge without
  creating a service or deleting pairing data. The script entry point exits
  after UI/audio/job cleanup, so leftover executor threads cannot keep a
  closed assistant alive and prevent the next call from starting it.

Verification uses temporary device storage, loopback HTTP, fake launch effects,
real short-lived child processes, and offscreen Qt controls. The checks cover
unauthenticated/revoked rejection, fixed launch targets, duplicate startup,
exit-before-launch ordering, timeout refusal and desktop restart signals.
Source compilation and scoped undefined-name checks are also run. No test files
are added. Full phone-to-laptop calling and real assistant restart require a
device/application check after the update is loaded. Release lint passed with
zero errors. Owner-only voice authorization, the real assistant-readiness
signal and delivery of worker restart requests to the UI thread were checked.
The hidden listener and current-user logon registration were verified locally.
