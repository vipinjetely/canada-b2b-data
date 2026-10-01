from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]

REGISTRY = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "registry"
    / "quebec_registry.parquet"
)

DECISION_MAKERS = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "enrichment"
    / "decision_maker_sample.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "provenance"
)

REGISTRY_OUTPUT = (
    OUTPUT_DIR
    / "quebec_field_provenance.parquet"
)

DECISION_OUTPUT = (
    OUTPUT_DIR
    / "decision_maker_field_provenance.parquet"
)

METADATA_OUTPUT = (
    OUTPUT_DIR
    / "field_provenance_metadata.json"
)


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def main() -> None:

    print("=== V4 FIELD-LEVEL PROVENANCE BUILD ===")
    print()

    if not REGISTRY.exists():
        raise FileNotFoundError(
            f"Registry file not found: {REGISTRY}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path in [
        REGISTRY_OUTPUT,
        DECISION_OUTPUT,
    ]:
        if path.exists():
            path.unlink()

    con = duckdb.connect()

    try:

        registry_path = sql_path(REGISTRY)
        registry_output = sql_path(REGISTRY_OUTPUT)

        # --------------------------------------------------
        # REGISTRY FIELD PROVENANCE
        #
        # Long-form structure:
        #
        # registry_id
        # field_name
        # field_value
        # source_name
        # source_url
        # last_verified_at
        # evidence_type
        #
        # One provenance record per populated field.
        # --------------------------------------------------

        registry_fields = [
            ("legal_business_name", "legal_business_name"),
            ("registration_date", "registration_date"),
            ("constitution_date", "constitution_date"),
            ("registration_status", "registration_status"),
            ("legal_form", "legal_form"),
            ("employee_size_bucket", "employee_size_bucket"),
            ("primary_activity_code", "primary_activity_code"),
            ("primary_activity", "primary_activity"),
            ("secondary_activity_code", "secondary_activity_code"),
            ("secondary_activity", "secondary_activity"),
            (
                "registered_address_line_1",
                "registered_address_line_1",
            ),
            (
                "registered_address_line_2",
                "registered_address_line_2",
            ),
            (
                "registered_address_line_3",
                "registered_address_line_3",
            ),
            (
                "registered_address_line_4",
                "registered_address_line_4",
            ),
        ]

        selects = []

        for field_name, column_name in registry_fields:

            selects.append(
                f"""
                SELECT
                    CAST(registry_id AS VARCHAR)
                        AS registry_id,

                    '{field_name}'
                        AS field_name,

                    CAST({column_name} AS VARCHAR)
                        AS field_value,

                    'Quebec REQ'
                        AS source_name,

                    CAST(source_url AS VARCHAR)
                        AS source_url,

                    CAST(last_verified_at AS VARCHAR)
                        AS last_verified_at,

                    CAST(evidence_type AS VARCHAR)
                        AS evidence_type,

                    'REGISTRY_CONFIRMED'
                        AS verification_status

                FROM read_parquet(
                    '{registry_path}'
                )

                WHERE {column_name} IS NOT NULL
                  AND TRIM(
                        CAST({column_name} AS VARCHAR)
                      ) <> ''
                """
            )

        registry_union = "\nUNION ALL\n".join(
            selects
        )

        con.execute(
            f"""
            COPY (
                {registry_union}
            )
            TO '{registry_output}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        registry_provenance_rows = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(REGISTRY_OUTPUT)],
        ).fetchone()[0]

        registry_entities = con.execute(
            """
            SELECT COUNT(DISTINCT registry_id)
            FROM read_parquet(?)
            """,
            [str(REGISTRY_OUTPUT)],
        ).fetchone()[0]

        registry_field_counts = con.execute(
            """
            SELECT
                field_name,
                COUNT(*) AS records
            FROM read_parquet(?)
            GROUP BY field_name
            ORDER BY records DESC
            """,
            [str(REGISTRY_OUTPUT)],
        ).fetchall()

        # --------------------------------------------------
        # DECISION-MAKER FIELD PROVENANCE
        # --------------------------------------------------

        decision_rows = 0
        decision_entities = 0
        decision_field_counts = []

        if DECISION_MAKERS.exists():

            decision_path = sql_path(
                DECISION_MAKERS
            )

            decision_output = sql_path(
                DECISION_OUTPUT
            )

            decision_fields = [
                (
                    "person_name",
                    "person_name",
                ),
                (
                    "job_title",
                    "job_title",
                ),
                (
                    "role_category",
                    "role_category",
                ),
            ]

            decision_selects = []

            for (
                field_name,
                column_name,
            ) in decision_fields:

                decision_selects.append(
                    f"""
                    SELECT
                        CAST(registry_id AS VARCHAR)
                            AS registry_id,

                        CAST(business_name AS VARCHAR)
                            AS business_name,

                        CAST(person_name AS VARCHAR)
                            AS person_name,

                        '{field_name}'
                            AS field_name,

                        CAST({column_name} AS VARCHAR)
                            AS field_value,

                        CAST(source_type AS VARCHAR)
                            AS source_name,

                        CAST(evidence_url AS VARCHAR)
                            AS source_url,

                        CAST(verified_at_utc AS VARCHAR)
                            AS last_verified_at,

                        CAST(
                            verification_method
                            AS VARCHAR
                        )
                            AS evidence_type,

                        CAST(confidence AS VARCHAR)
                            AS verification_status

                    FROM read_csv_auto(
                        '{decision_path}',
                        HEADER=TRUE
                    )

                    WHERE {column_name} IS NOT NULL
                      AND TRIM(
                            CAST(
                                {column_name}
                                AS VARCHAR
                            )
                          ) <> ''
                    """
                )

            decision_union = (
                "\nUNION ALL\n".join(
                    decision_selects
                )
            )

            con.execute(
                f"""
                COPY (
                    {decision_union}
                )
                TO '{decision_output}'
                (
                    FORMAT PARQUET,
                    COMPRESSION ZSTD
                )
                """
            )

            decision_rows = con.execute(
                """
                SELECT COUNT(*)
                FROM read_parquet(?)
                """,
                [str(DECISION_OUTPUT)],
            ).fetchone()[0]

            decision_entities = con.execute(
                """
                SELECT
                    COUNT(
                        DISTINCT registry_id
                    )
                FROM read_parquet(?)
                """,
                [str(DECISION_OUTPUT)],
            ).fetchone()[0]

            decision_field_counts = (
                con.execute(
                    """
                    SELECT
                        field_name,
                        COUNT(*) AS records
                    FROM read_parquet(?)
                    GROUP BY field_name
                    ORDER BY records DESC
                    """,
                    [str(DECISION_OUTPUT)],
                ).fetchall()
            )

        # --------------------------------------------------
        # QUALITY CHECKS
        # --------------------------------------------------

        missing_registry_sources = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE source_url IS NULL
               OR TRIM(source_url) = ''
            """,
            [str(REGISTRY_OUTPUT)],
        ).fetchone()[0]

        missing_registry_verified = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE last_verified_at IS NULL
               OR TRIM(last_verified_at) = ''
            """,
            [str(REGISTRY_OUTPUT)],
        ).fetchone()[0]

        missing_decision_sources = 0
        missing_decision_verified = 0

        if DECISION_OUTPUT.exists():

            missing_decision_sources = (
                con.execute(
                    """
                    SELECT COUNT(*)
                    FROM read_parquet(?)
                    WHERE source_url IS NULL
                       OR TRIM(source_url) = ''
                    """,
                    [str(DECISION_OUTPUT)],
                ).fetchone()[0]
            )

            missing_decision_verified = (
                con.execute(
                    """
                    SELECT COUNT(*)
                    FROM read_parquet(?)
                    WHERE last_verified_at IS NULL
                       OR TRIM(last_verified_at) = ''
                    """,
                    [str(DECISION_OUTPUT)],
                ).fetchone()[0]
            )

    finally:
        con.close()

    # --------------------------------------------------
    # Metadata / audit evidence
    # --------------------------------------------------

    metadata = {
        "built_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "purpose":
            (
                "Field-level provenance for "
                "registry and decision-maker data."
            ),

        "registry": {
            "source":
                str(REGISTRY),

            "output":
                str(REGISTRY_OUTPUT),

            "entities":
                registry_entities,

            "provenance_rows":
                registry_provenance_rows,

            "missing_source_url":
                missing_registry_sources,

            "missing_last_verified_at":
                missing_registry_verified,

            "field_counts": {
                field: count
                for field, count
                in registry_field_counts
            },
        },

        "decision_makers": {
            "source":
                str(DECISION_MAKERS),

            "output":
                (
                    str(DECISION_OUTPUT)
                    if DECISION_OUTPUT.exists()
                    else None
                ),

            "entities":
                decision_entities,

            "provenance_rows":
                decision_rows,

            "missing_source_url":
                missing_decision_sources,

            "missing_last_verified_at":
                missing_decision_verified,

            "field_counts": {
                field: count
                for field, count
                in decision_field_counts
            },
        },

        "schema": {
            "registry_id":
                "Entity identifier",

            "field_name":
                "Name of enriched field",

            "field_value":
                "Observed field value",

            "source_name":
                "Source responsible for field",

            "source_url":
                "Evidence/source URL",

            "last_verified_at":
                "Timestamp when source was collected or verified",

            "evidence_type":
                "Type of supporting evidence",

            "verification_status":
                "Confidence / verification class",
        },
    }

    METADATA_OUTPUT.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------
    # Report
    # --------------------------------------------------

    print("=== REGISTRY PROVENANCE ===")
    print()

    print(
        f"Entities              : "
        f"{registry_entities:,}"
    )

    print(
        f"Field evidence rows   : "
        f"{registry_provenance_rows:,}"
    )

    print(
        f"Missing source URLs   : "
        f"{missing_registry_sources:,}"
    )

    print(
        f"Missing verified time : "
        f"{missing_registry_verified:,}"
    )

    print()
    print("Field coverage:")

    for field, count in registry_field_counts:
        print(
            f"  {field:<30} "
            f"{count:>12,}"
        )

    print()

    print("=== DECISION-MAKER PROVENANCE ===")
    print()

    print(
        f"Entities              : "
        f"{decision_entities:,}"
    )

    print(
        f"Field evidence rows   : "
        f"{decision_rows:,}"
    )

    print(
        f"Missing source URLs   : "
        f"{missing_decision_sources:,}"
    )

    print(
        f"Missing verified time : "
        f"{missing_decision_verified:,}"
    )

    if decision_field_counts:
        print()
        print("Field coverage:")

        for (
            field,
            count,
        ) in decision_field_counts:

            print(
                f"  {field:<30} "
                f"{count:>12,}"
            )

    print()
    print(
        f"Registry output       : "
        f"{REGISTRY_OUTPUT}"
    )

    print(
        f"Decision output       : "
        f"{DECISION_OUTPUT}"
    )

    print(
        f"Metadata              : "
        f"{METADATA_OUTPUT}"
    )

    print()
    print(
        "=== V4 FIELD-LEVEL PROVENANCE SUCCESS ==="
    )


if __name__ == "__main__":
    main()