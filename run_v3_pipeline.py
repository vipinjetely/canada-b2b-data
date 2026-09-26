from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Production V3 transformation stages only.
#
# Intentionally excluded:
# - raw Overture download
# - audit scripts
# - sample/pilot scripts
# - decision-maker extraction (still REVIEW-only)
#
# V3 PostgreSQL tables are refreshed only after all transformation
# and enrichment stages complete successfully.
# Existing V1/V2 tables are not modified.
STAGES = [
    ("Classify Canadian Overture places", "classify_overture_canada.py"),
    ("Build strict business candidates", "classify_overture_businesses_v2.py"),
    ("Prepare employee enrichment fields", "build_v3_employee_base.py"),
    ("Build operating-location layer", "build_v3_location_layer.py"),
    ("Build entity-resolution foundation", "build_v3_entity_resolution_base.py"),
    ("Build verified Vancouver employee matches", "build_vancouver_employee_enrichment.py"),
    ("Apply verified employee enrichment", "apply_vancouver_employee_enrichment.py"),
    ("Score record quality and readiness", "score_v3_business_quality.py"),
    ("Detect daily new and changed businesses", "detect_v3_changes.py"),
    ("Persist daily change history", "database/load_v3_change_history.py"),
    ("Load validated V3 data into PostgreSQL", "database/load_v3_postgres.py"),
]


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_log(log_file: Path, message: str) -> None:
    print(message, flush=True)

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")


def run_stage(
    number: int,
    total: int,
    title: str,
    script_name: str,
    log_file: Path,
) -> None:
    script_path = PROJECT_ROOT / script_name

    if not script_path.exists():
        raise FileNotFoundError(
            f"Required V3 script not found: {script_path}"
        )

    write_log(
        log_file,
        f"\n[{number}/{total}] START — {title}",
    )
    write_log(
        log_file,
        f"Script: {script_name}",
    )

    started = time.perf_counter()

    process = subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    assert process.stdout is not None

    with log_file.open("a", encoding="utf-8") as handle:
        for line in process.stdout:
            print(line, end="", flush=True)
            handle.write(line)

    return_code = process.wait()
    elapsed = time.perf_counter() - started

    if return_code != 0:
        raise RuntimeError(
            f"{script_name} failed with exit code "
            f"{return_code}"
        )

    write_log(
        log_file,
        f"[{number}/{total}] PASS — {title} "
        f"({elapsed:.1f}s)",
    )


def main() -> int:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"v3_pipeline_{run_id}.log"

    write_log(
        log_file,
        "=== CANADA B2B V3 PIPELINE ===",
    )
    write_log(
        log_file,
        f"Run ID : {run_id}",
    )
    write_log(
        log_file,
        f"Started: {timestamp()}",
    )
    write_log(
        log_file,
        f"Python : {sys.executable}",
    )
    write_log(
        log_file,
        f"Root   : {PROJECT_ROOT}",
    )

    pipeline_started = time.perf_counter()

    try:
        for number, (title, script_name) in enumerate(
            STAGES,
            start=1,
        ):
            run_stage(
                number,
                len(STAGES),
                title,
                script_name,
                log_file,
            )

    except Exception as exc:
        elapsed = time.perf_counter() - pipeline_started

        write_log(
            log_file,
            "\n=== V3 PIPELINE FAILED ===",
        )
        write_log(
            log_file,
            f"Finished: {timestamp()}",
        )
        write_log(
            log_file,
            f"Elapsed : {elapsed:.1f}s",
        )
        write_log(
            log_file,
            f"Error   : {exc}",
        )
        write_log(
            log_file,
            f"Log     : {log_file}",
        )

        return 1

    elapsed = time.perf_counter() - pipeline_started

    write_log(
        log_file,
        "\n=== V3 PIPELINE SUCCESS ===",
    )
    write_log(
        log_file,
        f"Finished: {timestamp()}",
    )
    write_log(
        log_file,
        f"Elapsed : {elapsed:.1f}s",
    )
    write_log(
        log_file,
        f"Stages  : {len(STAGES)}/{len(STAGES)} passed",
    )
    write_log(
        log_file,
        f"Log     : {log_file}",
    )
    write_log(
        log_file,
        "Database: validated V3 data loaded into PostgreSQL",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())