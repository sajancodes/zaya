"""Zaya OpenCode Live Terminal — Real-time visible console viewer for coding jobs.
Created and developed by Sajan Rai for Zaya.

Displays live tool executions, file edits, model responses, and supervisor reviews
in a dedicated visible console window so the owner can watch the actual work.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.runtime_paths import mutable_path


def get_stream_path(job_id: str) -> Path:
    return mutable_path(ROOT / 'memory' / f'opencode_stream_{job_id}.log')


def stream_log(job_id: str, *, once: bool = False, poll_interval: float = 0.25) -> None:
    path = get_stream_path(job_id)

    print("=" * 70, flush=True)
    print(f"               ZAYA OPENCODE LIVE TERMINAL", flush=True)
    print(f"      Job: {job_id} | Created and developed by Sajan Rai", flush=True)
    print("=" * 70, flush=True)
    print(f"[Terminal] Watching live execution stream: {path.name}", flush=True)
    print("-" * 70, flush=True)

    position = 0
    waiting_shown = False
    deadline = time.monotonic() + 300  # 5 min max idle

    while True:
        try:
            if not path.exists():
                if not waiting_shown:
                    print("[Terminal] Waiting for OpenCode process to begin streaming...", flush=True)
                    waiting_shown = True
                if once:
                    break
                time.sleep(poll_interval)
                continue

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(position)
                chunk = f.read()
                if chunk:
                    print(chunk, end="", flush=True)
                    position = f.tell()
                    waiting_shown = False

            if once:
                break

            time.sleep(poll_interval)
        except KeyboardInterrupt:
            print("\n[Terminal] Live viewer detached by owner.", flush=True)
            break
        except Exception as e:
            print(f"\n[Terminal] Read error: {e}", flush=True)
            if once:
                break
            time.sleep(1.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Live console viewer for Zaya OpenCode sessions")
    parser.add_argument("--job", required=True, help="Job ID to monitor")
    parser.add_argument("--once", action="store_true", help="Print existing content and exit")
    args = parser.parse_args()

    stream_log(args.job, once=args.once)


if __name__ == "__main__":
    main()
