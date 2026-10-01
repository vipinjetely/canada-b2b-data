from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed" / "v4"

FEDERAL = DATA / "registry" / "federal_registry.parquet"
QUEBEC = DATA / "registry" / "quebec_registry.parquet"

NEW_BUSINESS = (
    DATA
    / "new_businesses"
    / "quebec_new_business_detection.json"
)

DECISION_SAMPLE = (
    DATA
    / "enrichment"
    / "decision_maker_sample.csv"
)

DECISION_EVIDENCE = (
    DATA
    / "enrichment"
    / "decision_maker_sample_evidence.json"
)

PROVENANCE = (
    DATA
    / "provenance"
    / "quebec_field_provenance.parquet"
)

DECISION_PROVENANCE = (
    DATA
    / "provenance"
    / "decision_maker_field_provenance.parquet"
)

WEBSITE_CLEAN = (
    DATA
    / "website_quality"
    / "business_locations_websites_cleaned.parquet"
)

WEBSITE_QUARANTINE = (
    DATA
    / "website_quality"
    / "website_quarantine.parquet"
)

WEBSITE_AUDIT = (
    DATA
    / "website_quality"
    / "website_cleanup_audit.json"
)

OUTPUT_DIR = DATA / "audit"

OUTPUT_JSON = (
    OUTPUT_DIR
    / "karan_six_point_validation.json"
)


def result(
    point: int,
    title: str,
    passed: bool,
    evidence: dict,
) -> dict:

    return {
        "point": point,
        "title": title,
        "status": "PASS" if passed else "FAIL",
        "evidence": evidence,
    }


def require_file(path: Path) -> None:

    if not path.exists():
        raise FileNotFoundError(
            f"Required audit artifact missing: {path}"
        )


def main() -> None:

    print("=== KARAN SIX-POINT FINAL VALIDATION ===")
    print()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    con = duckdb.connect()

    results = []

    try:

        # ==================================================
        # POINT 1
        # Registry integration
        # ==================================================

        require_file(QUEBEC)

        quebec_rows = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(QUEBEC)],
        ).fetchone()[0]

        quebec_unique = con.execute(
            """
            SELECT COUNT(DISTINCT registry_id)
            FROM read_parquet(?)
            """,
            [str(QUEBEC)],
        ).fetchone()[0]

        federal_exists = FEDERAL.exists()

        federal_rows = 0

        if federal_exists:

            federal_rows = con.execute(
                """
                SELECT COUNT(*)
                FROM read_parquet(?)
                """,
                [str(FEDERAL)],
            ).fetchone()[0]

        point1_pass = (
            quebec_rows > 0
            and quebec_rows == quebec_unique
        )

        results.append(
            result(
                1,
                "Registry integration",
                point1_pass,
                {
                    "quebec_registry_records":
                        quebec_rows,

                    "quebec_unique_registry_ids":
                        quebec_unique,

                    "quebec_duplicate_registry_ids":
                        quebec_rows - quebec_unique,

                    "federal_registry_available":
                        federal_exists,

                    "federal_registry_records":
                        federal_rows,
                },
            )
        )

        # ==================================================
        # POINT 2
        # New-business detection + freshness
        # ==================================================

        require_file(NEW_BUSINESS)

        new_business_data = json.loads(
            NEW_BUSINESS.read_text(
                encoding="utf-8"
            )
        )

        latest_source_date = (
            new_business_data.get(
                "dataset_latest_registration_date"
            )
        )

        source_lag = (
            new_business_data.get(
                "source_lag_days"
            )
        )

        calendar_today = (
            new_business_data.get(
                "calendar_today"
            )
        )

        calendar_windows = (
            new_business_data.get(
                "calendar_windows",
                {},
            )
        )

        dataset_relative_windows = (
            new_business_data.get(
                "dataset_relative_windows",
                {},
            )
        )

        today_data = (
            calendar_windows.get(
                "today",
                {},
            )
        )

        last_7_data = (
            calendar_windows.get(
                "last_7_days",
                {},
            )
        )

        last_30_data = (
            calendar_windows.get(
                "last_30_days",
                {},
            )
        )

        latest_7_data = (
            dataset_relative_windows.get(
                "latest_7_days",
                {},
            )
        )

        latest_30_data = (
            dataset_relative_windows.get(
                "latest_30_days",
                {},
            )
        )

        today_count = (
            today_data.get("count")
        )

        last_7_days_count = (
            last_7_data.get("count")
        )

        last_30_days_count = (
            last_30_data.get("count")
        )

        latest_dataset_7_days = (
            latest_7_data.get("count")
        )

        latest_dataset_30_days = (
            latest_30_data.get("count")
        )

        point2_required_values = [
            latest_source_date,
            source_lag,
            calendar_today,
            today_count,
            last_7_days_count,
            last_30_days_count,
            latest_dataset_7_days,
            latest_dataset_30_days,
        ]

        point2_pass = all(
            value is not None
            for value in point2_required_values
        )

        results.append(
            result(
                2,
                "New-business detection and freshness",
                point2_pass,
                {
                    "calendar_today":
                        calendar_today,

                    "latest_source_date":
                        latest_source_date,

                    "source_lag_days":
                        source_lag,

                    "calendar_today_count":
                        today_count,

                    "calendar_last_7_days":
                        last_7_days_count,

                    "calendar_last_30_days":
                        last_30_days_count,

                    "dataset_relative_last_7_days":
                        latest_dataset_7_days,

                    "dataset_relative_last_30_days":
                        latest_dataset_30_days,

                    "evidence_file":
                        str(NEW_BUSINESS),
                },
            )
        )

        # ==================================================
        # POINT 3
        # Employee-size classification
        # ==================================================

        employee_total = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(QUEBEC)],
        ).fetchone()[0]

        employee_verified = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE employee_size_verified = TRUE
            """,
            [str(QUEBEC)],
        ).fetchone()[0]

        employee_bucket_present = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)

            WHERE employee_size_bucket IS NOT NULL

              AND LENGTH(
                    TRIM(
                        CAST(
                            employee_size_bucket
                            AS VARCHAR
                        )
                    )
                  ) > 0
            """,
            [str(QUEBEC)],
        ).fetchone()[0]

        employee_count_types = con.execute(
            """
            SELECT
                employee_count_type,
                COUNT(*) AS records

            FROM read_parquet(?)

            GROUP BY employee_count_type

            ORDER BY records DESC
            """,
            [str(QUEBEC)],
        ).fetchall()

        point3_pass = (
            employee_verified > 0
            and employee_bucket_present > 0
        )

        results.append(
            result(
                3,
                "Employee-size classification",
                point3_pass,
                {
                    "registry_records":
                        employee_total,

                    "verified_employee_ranges":
                        employee_verified,

                    "records_with_employee_bucket":
                        employee_bucket_present,

                    "employee_count_types": {
                        str(key): value
                        for key, value
                        in employee_count_types
                    },
                },
            )
        )

        # ==================================================
        # POINT 4
        # Evidence-backed decision-maker enrichment
        # ==================================================

        require_file(DECISION_SAMPLE)

        decision_rows = con.execute(
            """
            SELECT COUNT(*)

            FROM read_csv_auto(
                ?,
                HEADER=TRUE
            )
            """,
            [str(DECISION_SAMPLE)],
        ).fetchone()[0]

        decision_entities = con.execute(
            """
            SELECT COUNT(
                DISTINCT registry_id
            )

            FROM read_csv_auto(
                ?,
                HEADER=TRUE
            )
            """,
            [str(DECISION_SAMPLE)],
        ).fetchone()[0]

        missing_decision_url = con.execute(
            """
            SELECT COUNT(*)

            FROM read_csv_auto(
                ?,
                HEADER=TRUE
            )

            WHERE evidence_url IS NULL

               OR LENGTH(
                    TRIM(
                        CAST(
                            evidence_url
                            AS VARCHAR
                        )
                    )
                  ) = 0
            """,
            [str(DECISION_SAMPLE)],
        ).fetchone()[0]

        missing_person = con.execute(
            """
            SELECT COUNT(*)

            FROM read_csv_auto(
                ?,
                HEADER=TRUE
            )

            WHERE person_name IS NULL

               OR LENGTH(
                    TRIM(
                        CAST(
                            person_name
                            AS VARCHAR
                        )
                    )
                  ) = 0
            """,
            [str(DECISION_SAMPLE)],
        ).fetchone()[0]

        missing_title = con.execute(
            """
            SELECT COUNT(*)

            FROM read_csv_auto(
                ?,
                HEADER=TRUE
            )

            WHERE job_title IS NULL

               OR LENGTH(
                    TRIM(
                        CAST(
                            job_title
                            AS VARCHAR
                        )
                    )
                  ) = 0
            """,
            [str(DECISION_SAMPLE)],
        ).fetchone()[0]

        point4_pass = (
            decision_rows > 0
            and missing_decision_url == 0
            and missing_person == 0
            and missing_title == 0
        )

        results.append(
            result(
                4,
                "Evidence-backed decision-maker enrichment",
                point4_pass,
                {
                    "accepted_decision_makers":
                        decision_rows,

                    "covered_business_entities":
                        decision_entities,

                    "missing_person_name":
                        missing_person,

                    "missing_job_title":
                        missing_title,

                    "missing_evidence_url":
                        missing_decision_url,

                    "sample_file":
                        str(DECISION_SAMPLE),

                    "evidence_file_available":
                        DECISION_EVIDENCE.exists(),
                },
            )
        )

        # ==================================================
        # POINT 5
        # Per-field source + last-verified provenance
        # ==================================================

        require_file(PROVENANCE)
        require_file(DECISION_PROVENANCE)

        provenance_rows = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(PROVENANCE)],
        ).fetchone()[0]

        provenance_entities = con.execute(
            """
            SELECT COUNT(
                DISTINCT registry_id
            )
            FROM read_parquet(?)
            """,
            [str(PROVENANCE)],
        ).fetchone()[0]

        provenance_missing_source = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)

            WHERE source_url IS NULL
               OR LENGTH(
                    TRIM(source_url)
                  ) = 0
            """,
            [str(PROVENANCE)],
        ).fetchone()[0]

        provenance_missing_verified = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)

            WHERE last_verified_at IS NULL
               OR LENGTH(
                    TRIM(last_verified_at)
                  ) = 0
            """,
            [str(PROVENANCE)],
        ).fetchone()[0]

        decision_provenance_rows = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(DECISION_PROVENANCE)],
        ).fetchone()[0]

        decision_provenance_entities = con.execute(
            """
            SELECT COUNT(
                DISTINCT registry_id
            )
            FROM read_parquet(?)
            """,
            [str(DECISION_PROVENANCE)],
        ).fetchone()[0]

        decision_provenance_missing_source = (
            con.execute(
                """
                SELECT COUNT(*)
                FROM read_parquet(?)

                WHERE source_url IS NULL
                   OR LENGTH(
                        TRIM(source_url)
                      ) = 0
                """,
                [str(DECISION_PROVENANCE)],
            ).fetchone()[0]
        )

        decision_provenance_missing_verified = (
            con.execute(
                """
                SELECT COUNT(*)
                FROM read_parquet(?)

                WHERE last_verified_at IS NULL
                   OR LENGTH(
                        TRIM(last_verified_at)
                      ) = 0
                """,
                [str(DECISION_PROVENANCE)],
            ).fetchone()[0]
        )

        point5_pass = (
            provenance_rows > 0
            and provenance_missing_source == 0
            and provenance_missing_verified == 0
            and decision_provenance_rows > 0
            and decision_provenance_missing_source == 0
            and decision_provenance_missing_verified == 0
        )

        results.append(
            result(
                5,
                "Per-field source and last-verified provenance",
                point5_pass,
                {
                    "registry_entities":
                        provenance_entities,

                    "registry_field_evidence_rows":
                        provenance_rows,

                    "registry_missing_source_url":
                        provenance_missing_source,

                    "registry_missing_last_verified":
                        provenance_missing_verified,

                    "decision_entities":
                        decision_provenance_entities,

                    "decision_field_evidence_rows":
                        decision_provenance_rows,

                    "decision_missing_source_url":
                        decision_provenance_missing_source,

                    "decision_missing_last_verified":
                        decision_provenance_missing_verified,
                },
            )
        )

        # ==================================================
        # POINT 6
        # Directory/social website filtering
        # ==================================================

        require_file(WEBSITE_CLEAN)
        require_file(WEBSITE_QUARANTINE)
        require_file(WEBSITE_AUDIT)

        website_audit = json.loads(
            WEBSITE_AUDIT.read_text(
                encoding="utf-8"
            )
        )

        source_rows = website_audit.get(
            "source_rows"
        )

        cleaned_rows = website_audit.get(
            "cleaned_rows"
        )

        quarantined = website_audit.get(
            "websites_quarantined"
        )

        blocked_remaining = website_audit.get(
            "blocked_domains_remaining"
        )

        row_preserved = website_audit.get(
            "row_count_preserved"
        )

        websites_before = website_audit.get(
            "website_nonblank_before"
        )

        websites_after = website_audit.get(
            "website_nonblank_after"
        )

        karan_flagged = website_audit.get(
            "karan_specifically_flagged_categories"
        )

        quarantine_rows = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(WEBSITE_QUARANTINE)],
        ).fetchone()[0]

        cleaned_actual_rows = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(WEBSITE_CLEAN)],
        ).fetchone()[0]

        point6_pass = (
            source_rows == cleaned_rows
            and cleaned_rows == cleaned_actual_rows
            and row_preserved is True
            and quarantined == quarantine_rows
            and blocked_remaining == 0
        )

        results.append(
            result(
                6,
                "Directory/social website filtering",
                point6_pass,
                {
                    "source_rows":
                        source_rows,

                    "cleaned_rows":
                        cleaned_rows,

                    "verified_cleaned_rows":
                        cleaned_actual_rows,

                    "row_count_preserved":
                        row_preserved,

                    "websites_quarantined":
                        quarantined,

                    "verified_quarantine_rows":
                        quarantine_rows,

                    "blocked_domains_remaining":
                        blocked_remaining,

                    "websites_before":
                        websites_before,

                    "websites_after":
                        websites_after,

                    "karan_flagged_categories":
                        karan_flagged,

                    "rejection_reason_counts":
                        website_audit.get(
                            "rejection_reason_counts",
                            {},
                        ),
                },
            )
        )

    finally:
        con.close()

    # ======================================================
    # FINAL RESULT
    # ======================================================

    passed = sum(
        1
        for item in results
        if item["status"] == "PASS"
    )

    failed = (
        len(results) - passed
    )

    overall = (
        "PASS"
        if failed == 0
        else "FAIL"
    )

    report = {
        "validated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "overall_status":
            overall,

        "points_passed":
            passed,

        "points_failed":
            failed,

        "total_points":
            len(results),

        "results":
            results,
    }

    OUTPUT_JSON.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    # ======================================================
    # CONSOLE REPORT
    # ======================================================

    print("FINAL RESULTS")
    print("=" * 70)

    for item in results:

        print(
            f"[{item['status']}] "
            f"Point #{item['point']} - "
            f"{item['title']}"
        )

    print("=" * 70)

    print(
        f"Passed : {passed}/6"
    )

    print(
        f"Failed : {failed}/6"
    )

    print(
        f"Overall: {overall}"
    )

    print()

    # Useful headline evidence for demo.
    print("HEADLINE EVIDENCE")
    print("=" * 70)

    print(
        f"Quebec registry records        : "
        f"{quebec_rows:,}"
    )

    print(
        f"Latest registration date       : "
        f"{latest_source_date}"
    )

    print(
        f"Source freshness lag           : "
        f"{source_lag} day(s)"
    )

    print(
        f"Latest dataset 7-day businesses: "
        f"{latest_dataset_7_days:,}"
    )

    print(
        f"Latest dataset 30-day businesses: "
        f"{latest_dataset_30_days:,}"
    )

    print(
        f"Verified employee ranges       : "
        f"{employee_verified:,}"
    )

    print(
        f"Decision-makers demonstrated   : "
        f"{decision_rows:,}"
    )

    print(
        f"Registry provenance rows       : "
        f"{provenance_rows:,}"
    )

    print(
        f"Missing provenance sources     : "
        f"{provenance_missing_source:,}"
    )

    print(
        f"Missing provenance timestamps  : "
        f"{provenance_missing_verified:,}"
    )

    print(
        f"Websites quarantined           : "
        f"{quarantined:,}"
    )

    print(
        f"Blocked websites remaining     : "
        f"{blocked_remaining:,}"
    )

    print(
        f"Business rows preserved        : "
        f"{cleaned_rows:,}"
    )

    print("=" * 70)

    print()
    print(
        f"Evidence report: {OUTPUT_JSON}"
    )

    print()

    if failed:

        raise RuntimeError(
            "One or more Karan validation "
            "points failed."
        )

    print(
        "=== KARAN SIX-POINT VALIDATION SUCCESS ==="
    )


if __name__ == "__main__":
    main()