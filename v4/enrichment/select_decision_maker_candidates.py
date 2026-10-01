from __future__ import annotations

import csv
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
    / "enrichment"
)

OUTPUT = OUTPUT_DIR / "decision_maker_candidates.csv"
EVIDENCE = OUTPUT_DIR / "decision_maker_candidates_evidence.json"

TARGET_COUNT = 20


def main() -> None:
    print("=== V4 DECISION-MAKER CANDIDATE SELECTION ===")
    print()

    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Quebec registry not found: {SOURCE}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    con = duckdb.connect()

    try:
        latest_date = con.execute(
            """
            SELECT MAX(registration_date)
            FROM read_parquet(?)
            """,
            [str(SOURCE)],
        ).fetchone()[0]

        if latest_date is None:
            raise RuntimeError(
                "No registration dates available."
            )

        rows = con.execute(
            """
            SELECT
                registry_id,
                neq,
                legal_business_name,
                registration_date,
                constitution_date,
                registration_status,
                legal_form,
                employee_size_code,
                employee_size_bucket,
                employee_count_type,
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
                last_verified_at

            FROM read_parquet(?)

            WHERE is_currently_registered = TRUE

              AND legal_business_name IS NOT NULL
              AND TRIM(legal_business_name) <> ''

              AND registration_date IS NOT NULL

              AND employee_size_verified = TRUE

              AND employee_size_code IN (
                    'B',
                    'C',
                    'D',
                    'E',
                    'F',
                    'G',
                    'H',
                    'I',
                    'J',
                    'K',
                    'L'
              )

              AND primary_activity IS NOT NULL
              AND TRIM(primary_activity) <> ''

            ORDER BY
                registration_date DESC,

                CASE employee_size_code
                    WHEN 'L' THEN 1
                    WHEN 'K' THEN 2
                    WHEN 'J' THEN 3
                    WHEN 'I' THEN 4
                    WHEN 'H' THEN 5
                    WHEN 'G' THEN 6
                    WHEN 'F' THEN 7
                    WHEN 'E' THEN 8
                    WHEN 'D' THEN 9
                    WHEN 'C' THEN 10
                    WHEN 'B' THEN 11
                    ELSE 99
                END,

                registry_id

            LIMIT ?
            """,
            [
                str(SOURCE),
                TARGET_COUNT,
            ],
        ).fetchall()

        columns = [
            item[0]
            for item in con.description
        ]

    finally:
        con.close()

    if not rows:
        raise RuntimeError(
            "No suitable decision-maker candidates found."
        )

    records = [
        dict(zip(columns, row))
        for row in rows
    ]

    output_columns = [
        "candidate_id",
        "registry_id",
        "neq",
        "business_name",
        "registration_date",
        "constitution_date",
        "registration_status",
        "legal_form",
        "employee_size_code",
        "employee_size_bucket",
        "primary_activity_code",
        "primary_activity",
        "declared_primary_activity",
        "secondary_activity_code",
        "secondary_activity",
        "registered_address",
        "registry_source_url",
        "registry_last_verified_at",
        "company_website",
        "company_website_source",
        "target_role_1",
        "target_role_2",
        "target_role_3",
        "discovery_status",
    ]

    with OUTPUT.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=output_columns,
        )

        writer.writeheader()

        for index, record in enumerate(
            records,
            start=1,
        ):
            address_parts = [
                record.get("registered_address_line_1"),
                record.get("registered_address_line_2"),
                record.get("registered_address_line_3"),
                record.get("registered_address_line_4"),
            ]

            address = ", ".join(
                str(value).strip()
                for value in address_parts
                if value and str(value).strip()
            )

            writer.writerow(
                {
                    "candidate_id":
                        f"QC-DM-{index:03d}",

                    "registry_id":
                        record["registry_id"],

                    "neq":
                        record["neq"],

                    "business_name":
                        record["legal_business_name"],

                    "registration_date":
                        record["registration_date"],

                    "constitution_date":
                        record["constitution_date"],

                    "registration_status":
                        record["registration_status"],

                    "legal_form":
                        record["legal_form"],

                    "employee_size_code":
                        record["employee_size_code"],

                    "employee_size_bucket":
                        record["employee_size_bucket"],

                    "primary_activity_code":
                        record["primary_activity_code"],

                    "primary_activity":
                        record["primary_activity"],

                    "declared_primary_activity":
                        record["declared_primary_activity"],

                    "secondary_activity_code":
                        record["secondary_activity_code"],

                    "secondary_activity":
                        record["secondary_activity"],

                    "registered_address":
                        address,

                    "registry_source_url":
                        record["source_url"],

                    "registry_last_verified_at":
                        record["last_verified_at"],

                    "company_website":
                        "",

                    "company_website_source":
                        "",

                    "target_role_1":
                        "OWNER_OR_EXECUTIVE",

                    "target_role_2":
                        "OPERATIONS",

                    "target_role_3":
                        "IT_OR_PROCUREMENT",

                    "discovery_status":
                        "PENDING_PUBLIC_DISCOVERY",
                }
            )

    evidence = {
        "built_at_utc":
            datetime.now(timezone.utc).isoformat(),

        "source":
            str(SOURCE),

        "output":
            str(OUTPUT),

        "latest_registry_date":
            latest_date.isoformat(),

        "candidate_count":
            len(records),

        "selection_rules": [
            "currently registered",
            "legal business name present",
            "official registration date present",
            "registry-confirmed employee range",
            "employee range starts at 6 employees",
            "primary economic activity present",
            "newer registrations preferred",
            "larger employee ranges preferred within same date",
        ],

        "decision_maker_policy": {
            "person_names_generated": False,
            "titles_generated": False,
            "public_evidence_required": True,

            "target_roles": [
                "owner/executive",
                "general manager",
                "IT",
                "operations",
                "procurement/purchasing",
            ],
        },
    }

    EVIDENCE.write_text(
        json.dumps(
            evidence,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"Latest registry date : {latest_date}")
    print(f"Candidates selected  : {len(records):,}")
    print()
    print(f"Output               : {OUTPUT}")
    print(f"Evidence             : {EVIDENCE}")

    print()
    print("Candidate preview:")
    print()

    for index, record in enumerate(
        records[:10],
        start=1,
    ):
        print(
            f"{index:02d}. "
            f"{record['legal_business_name']} | "
            f"{record['employee_size_bucket']} | "
            f"{record['primary_activity']}"
        )

    print()
    print(
        "=== V4 DECISION-MAKER "
        "CANDIDATE SELECTION SUCCESS ==="
    )


if __name__ == "__main__":
    main()