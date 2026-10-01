from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "registry"
    / "quebec_registry.parquet"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "new_businesses"
)

TODAY_OUTPUT = OUTPUT_DIR / "quebec_new_today.parquet"
LAST_7_OUTPUT = OUTPUT_DIR / "quebec_new_last_7_days.parquet"
LAST_30_OUTPUT = OUTPUT_DIR / "quebec_new_last_30_days.parquet"

DATASET_7_OUTPUT = (
    OUTPUT_DIR
    / "quebec_new_latest_dataset_7_days.parquet"
)

DATASET_30_OUTPUT = (
    OUTPUT_DIR
    / "quebec_new_latest_dataset_30_days.parquet"
)

EVIDENCE_OUTPUT = (
    OUTPUT_DIR
    / "quebec_new_business_detection.json"
)


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def main() -> None:
    print("=== V4 QUEBEC NEW-BUSINESS DETECTION ===")
    print()

    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Quebec registry parquet not found: {SOURCE}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in [
        TODAY_OUTPUT,
        LAST_7_OUTPUT,
        LAST_30_OUTPUT,
        DATASET_7_OUTPUT,
        DATASET_30_OUTPUT,
    ]:
        if path.exists():
            path.unlink()

    run_time = datetime.now(timezone.utc)
    calendar_today = run_time.date()

    con = duckdb.connect()

    try:
        # --------------------------------------------------
        # Source validation
        # --------------------------------------------------

        total_records = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(SOURCE)],
        ).fetchone()[0]

        dated_records = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE registration_date IS NOT NULL
            """,
            [str(SOURCE)],
        ).fetchone()[0]

        latest_registration_date = con.execute(
            """
            SELECT MAX(registration_date)
            FROM read_parquet(?)
            """,
            [str(SOURCE)],
        ).fetchone()[0]

        earliest_registration_date = con.execute(
            """
            SELECT MIN(registration_date)
            FROM read_parquet(?)
            """,
            [str(SOURCE)],
        ).fetchone()[0]

        if latest_registration_date is None:
            raise RuntimeError(
                "No registration dates found in Quebec registry."
            )

        print(f"Registry records       : {total_records:,}")
        print(f"Records with date      : {dated_records:,}")
        print(
            f"Earliest registration  : "
            f"{earliest_registration_date}"
        )
        print(
            f"Latest registration    : "
            f"{latest_registration_date}"
        )
        print(f"Calendar today         : {calendar_today}")
        print()

        # --------------------------------------------------
        # Reusable selected columns
        # --------------------------------------------------

        selected_columns = """
            registry_source,
            registry_id,
            neq,
            legal_business_name,
            registration_date,
            constitution_date,
            registration_status_code,
            registration_status,
            is_currently_registered,
            legal_form_code,
            legal_form,
            employee_size_code,
            employee_size_bucket,
            employee_count_type,
            employee_size_verified,
            primary_activity_code,
            primary_activity,
            declared_primary_activity,
            secondary_activity_code,
            secondary_activity,
            registered_address_line_1,
            registered_address_line_2,
            registered_address_line_3,
            registered_address_line_4,
            source_url,
            source_sha256,
            last_verified_at,
            evidence_type
        """

        source_path = sql_path(SOURCE)

        # --------------------------------------------------
        # Calendar TODAY
        # --------------------------------------------------

        con.execute(
            f"""
            COPY (
                SELECT
                    {selected_columns},
                    'CALENDAR_TODAY'
                        AS detection_window,
                    CURRENT_DATE
                        AS detection_reference_date

                FROM read_parquet(
                    '{source_path}'
                )

                WHERE registration_date
                    = CURRENT_DATE

                ORDER BY
                    registration_date DESC,
                    registry_id
            )
            TO '{sql_path(TODAY_OUTPUT)}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        # --------------------------------------------------
        # Calendar last 7 days
        #
        # Includes today and previous 6 calendar days.
        # --------------------------------------------------

        con.execute(
            f"""
            COPY (
                SELECT
                    {selected_columns},
                    'CALENDAR_LAST_7_DAYS'
                        AS detection_window,
                    CURRENT_DATE
                        AS detection_reference_date

                FROM read_parquet(
                    '{source_path}'
                )

                WHERE registration_date
                    BETWEEN
                        CURRENT_DATE - INTERVAL 6 DAY
                        AND CURRENT_DATE

                ORDER BY
                    registration_date DESC,
                    registry_id
            )
            TO '{sql_path(LAST_7_OUTPUT)}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        # --------------------------------------------------
        # Calendar last 30 days
        #
        # Includes today and previous 29 calendar days.
        # --------------------------------------------------

        con.execute(
            f"""
            COPY (
                SELECT
                    {selected_columns},
                    'CALENDAR_LAST_30_DAYS'
                        AS detection_window,
                    CURRENT_DATE
                        AS detection_reference_date

                FROM read_parquet(
                    '{source_path}'
                )

                WHERE registration_date
                    BETWEEN
                        CURRENT_DATE - INTERVAL 29 DAY
                        AND CURRENT_DATE

                ORDER BY
                    registration_date DESC,
                    registry_id
            )
            TO '{sql_path(LAST_30_OUTPUT)}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        # --------------------------------------------------
        # Dataset-relative 7-day window
        #
        # This is deliberately separate from "last 7 days".
        # It answers:
        # "What registrations appear in the newest 7-day
        # period represented by this dataset?"
        # --------------------------------------------------

        con.execute(
            f"""
            COPY (
                SELECT
                    {selected_columns},
                    'DATASET_LATEST_7_DAYS'
                        AS detection_window,

                    DATE '{latest_registration_date}'
                        AS detection_reference_date

                FROM read_parquet(
                    '{source_path}'
                )

                WHERE registration_date
                    BETWEEN
                        DATE '{latest_registration_date}'
                            - INTERVAL 6 DAY
                        AND
                        DATE '{latest_registration_date}'

                ORDER BY
                    registration_date DESC,
                    registry_id
            )
            TO '{sql_path(DATASET_7_OUTPUT)}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        # --------------------------------------------------
        # Dataset-relative 30-day window
        # --------------------------------------------------

        con.execute(
            f"""
            COPY (
                SELECT
                    {selected_columns},
                    'DATASET_LATEST_30_DAYS'
                        AS detection_window,

                    DATE '{latest_registration_date}'
                        AS detection_reference_date

                FROM read_parquet(
                    '{source_path}'
                )

                WHERE registration_date
                    BETWEEN
                        DATE '{latest_registration_date}'
                            - INTERVAL 29 DAY
                        AND
                        DATE '{latest_registration_date}'

                ORDER BY
                    registration_date DESC,
                    registry_id
            )
            TO '{sql_path(DATASET_30_OUTPUT)}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        # --------------------------------------------------
        # Counts
        # --------------------------------------------------

        today_count = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(TODAY_OUTPUT)],
        ).fetchone()[0]

        last_7_count = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(LAST_7_OUTPUT)],
        ).fetchone()[0]

        last_30_count = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(LAST_30_OUTPUT)],
        ).fetchone()[0]

        dataset_7_count = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(DATASET_7_OUTPUT)],
        ).fetchone()[0]

        dataset_30_count = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(DATASET_30_OUTPUT)],
        ).fetchone()[0]

        # --------------------------------------------------
        # Active/current registrations in each calendar
        # output. Useful for lead-oriented downstream use.
        # --------------------------------------------------

        active_today = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE is_currently_registered = TRUE
            """,
            [str(TODAY_OUTPUT)],
        ).fetchone()[0]

        active_7 = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE is_currently_registered = TRUE
            """,
            [str(LAST_7_OUTPUT)],
        ).fetchone()[0]

        active_30 = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE is_currently_registered = TRUE
            """,
            [str(LAST_30_OUTPUT)],
        ).fetchone()[0]

    finally:
        con.close()

    # ------------------------------------------------------
    # Freshness
    # ------------------------------------------------------

    source_lag_days = (
        calendar_today - latest_registration_date
    ).days

    # ------------------------------------------------------
    # Evidence JSON
    # ------------------------------------------------------

    evidence = {
        "source": str(SOURCE),

        "run_at_utc":
            run_time.isoformat(),

        "calendar_today":
            calendar_today.isoformat(),

        "dataset_earliest_registration_date":
            (
                earliest_registration_date.isoformat()
                if earliest_registration_date
                else None
            ),

        "dataset_latest_registration_date":
            latest_registration_date.isoformat(),

        "source_lag_days":
            source_lag_days,

        "total_registry_records":
            total_records,

        "records_with_registration_date":
            dated_records,

        "calendar_windows": {
            "today": {
                "count": today_count,
                "currently_registered":
                    active_today,
                "output":
                    str(TODAY_OUTPUT),
            },

            "last_7_days": {
                "definition":
                    "today plus previous 6 calendar days",
                "count": last_7_count,
                "currently_registered":
                    active_7,
                "output":
                    str(LAST_7_OUTPUT),
            },

            "last_30_days": {
                "definition":
                    "today plus previous 29 calendar days",
                "count": last_30_count,
                "currently_registered":
                    active_30,
                "output":
                    str(LAST_30_OUTPUT),
            },
        },

        "dataset_relative_windows": {
            "latest_7_days": {
                "reference_date":
                    latest_registration_date.isoformat(),
                "count":
                    dataset_7_count,
                "output":
                    str(DATASET_7_OUTPUT),
            },

            "latest_30_days": {
                "reference_date":
                    latest_registration_date.isoformat(),
                "count":
                    dataset_30_count,
                "output":
                    str(DATASET_30_OUTPUT),
            },
        },

        "methodology": {
            "new_business_definition":
                (
                    "A registry record whose official "
                    "Quebec REQ registration_date "
                    "(DAT_IMMAT) falls within the "
                    "specified calendar window."
                ),

            "important_limitation":
                (
                    "Calendar-window results depend on "
                    "the freshness of the source dataset. "
                    "Dataset-relative windows are reported "
                    "separately and must not be described "
                    "as calendar last-7/30-day results."
                ),
        },
    }

    EVIDENCE_OUTPUT.write_text(
        json.dumps(
            evidence,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ------------------------------------------------------
    # Report
    # ------------------------------------------------------

    print("=== CALENDAR WINDOWS ===")
    print()
    print(
        f"Today ({calendar_today})"
        f"             : {today_count:,}"
    )
    print(
        f"Last 7 calendar days"
        f"          : {last_7_count:,}"
    )
    print(
        f"Last 30 calendar days"
        f"         : {last_30_count:,}"
    )

    print()
    print("Currently registered within windows:")
    print(f"  Today                   : {active_today:,}")
    print(f"  Last 7 days             : {active_7:,}")
    print(f"  Last 30 days            : {active_30:,}")

    print()
    print("=== DATASET-RELATIVE WINDOWS ===")
    print()
    print(
        f"Dataset latest date       : "
        f"{latest_registration_date}"
    )
    print(
        f"Latest dataset 7 days     : "
        f"{dataset_7_count:,}"
    )
    print(
        f"Latest dataset 30 days    : "
        f"{dataset_30_count:,}"
    )

    print()
    print("=== FRESHNESS ===")
    print()
    print(
        f"Calendar today            : "
        f"{calendar_today}"
    )
    print(
        f"Latest source date        : "
        f"{latest_registration_date}"
    )
    print(
        f"Source lag                : "
        f"{source_lag_days:,} day(s)"
    )

    print()
    print(f"Evidence                  : {EVIDENCE_OUTPUT}")
    print()
    print(
        "=== V4 QUEBEC NEW-BUSINESS DETECTION SUCCESS ==="
    )


if __name__ == "__main__":
    main()