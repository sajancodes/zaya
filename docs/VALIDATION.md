# Zaya validation and rollback

Baseline: `a7daf25` on `zaya-updates`; inherited application baseline: `54733d5`.
The baseline had no automated tests. Core PyQt6, Google GenAI and sounddevice
imports passed on Windows. Live audio and external messaging require separate
canaries; imports and syntax checks do not prove those services work.

Run the regression suite with `python -m unittest discover -s tests -v`.
Tests use temporary files, processes and repositories; they do not send messages
or change personal memory. Each implementation phase is a separate commit.
Rollback with `git revert <phase-commit>` after inspecting dependent commits.
Do not reset the working tree or delete local config, memory or Hermes pairing.
