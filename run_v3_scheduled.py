from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOG_DIR = ROOT / "logs"
LOCK_FILE = LOG_DIR / "v3_scheduler.lock"
SCHEDULER_LOG = LOG_DIR / "v3_scheduler.log"
PIPELINE = ROOT / "run_v3_pipeline.py"

LOG_DIR.mkdir(exist_ok=True)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(message: str) -> None:
    line = f"[{now()}] {message}"
    print(line, flush=True)

    with SCHEDULER_LOG.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def acquire_lock() -> bool:
    try:
        fd = os.open(
            LOCK_FILE,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )

        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(
                f"pid={os.getpid()}\n"
                f"started={now()}\n"
            )

        return True

    except FileExistsError:
        return False


def release_lock() -> None:
    try:
        LOCK_FILE.unlink()
    except FileNotFoundError:
        pass


def main() -> int:
    if not PIPELINE.exists():
        log(f"FAILED — pipeline missing: {PIPELINE}")
        return 1

    if not acquire_lock():
        log(
            "SKIPPED — another V3 scheduled run "
            "appears to be active."
        )
        return 0

    log("START — scheduled V3 pipeline")

    try:
        completed = subprocess.run(
            [sys.executable, str(PIPELINE)],
            cwd=str(ROOT),
            check=False,
        )

        if completed.returncode != 0:
            log(
                "FAILED — V3 pipeline returned "
                f"exit code {completed.returncode}"
            )
            return completed.returncode

        log("SUCCESS — scheduled V3 pipeline completed")
        return 0

    except Exception as exc:
        log(f"FAILED — {type(exc).__name__}: {exc}")
        return 1

    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())