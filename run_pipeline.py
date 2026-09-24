import logging
import subprocess
import sys
import time
from pathlib import Path


LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "pipeline.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


PIPELINE_STAGES = [
    (
        "Collect Corporations Canada",
        "collectors/corporations_canada.py",
    ),
    (
        "Normalize Corporations Canada",
        "normalizers/corporations_canada.py",
    ),
    (
        "Deduplicate Corporations Canada",
        "deduplication/corporations_canada.py",
    ),
    (
        "Collect Statistics Canada ODBus",
        "collectors/statcan_odbus.py",
    ),
    (
        "Normalize Statistics Canada ODBus",
        "normalizers/statcan_odbus.py",
    ),
    (
        "Enrich Corporations Canada with ODBus",
        "enrichment/odbus_matcher.py",
    ),
    (
        "Load PostgreSQL",
        "database/load_businesses.py",
    ),
]


def run_stage(stage_name: str, script_path: str) -> None:
    logger.info("=" * 70)
    logger.info("STARTING: %s", stage_name)
    logger.info("Script: %s", script_path)

    start_time = time.perf_counter()

    result = subprocess.run(
        [sys.executable, script_path],
        text=True,
        capture_output=True,
    )

    duration = time.perf_counter() - start_time

    if result.stdout:
        for line in result.stdout.splitlines():
            logger.info("%s", line)

    if result.returncode != 0:
        if result.stderr:
            for line in result.stderr.splitlines():
                logger.error("%s", line)

        logger.error(
            "FAILED: %s after %.2f seconds",
            stage_name,
            duration,
        )

        raise RuntimeError(
            f"Pipeline stopped at stage: {stage_name}"
        )

    logger.info(
        "COMPLETED: %s in %.2f seconds",
        stage_name,
        duration,
    )


def main() -> None:
    logger.info("=" * 70)
    logger.info("CANADA B2B DATA PIPELINE STARTED")

    pipeline_start = time.perf_counter()

    try:
        for stage_name, script_path in PIPELINE_STAGES:
            run_stage(
                stage_name,
                script_path,
            )

    except Exception:
        logger.exception(
            "PIPELINE FAILED"
        )
        sys.exit(1)

    total_duration = (
        time.perf_counter() - pipeline_start
    )

    logger.info("=" * 70)
    logger.info(
        "PIPELINE COMPLETED SUCCESSFULLY"
    )
    logger.info(
        "Total runtime: %.2f seconds",
        total_duration,
    )
    logger.info(
        "Log file: %s",
        LOG_FILE,
    )


if __name__ == "__main__":
    main()