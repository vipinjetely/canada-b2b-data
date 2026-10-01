from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "data"
    / "raw"
    / "v2"
    / "corporations_canada_active.csv"
)

METADATA = (
    ROOT
    / "data"
    / "raw"
    / "v2"
    / "corporations_canada_metadata.json"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "registry"
)

OUTPUT = OUTPUT_DIR / "federal_registry.parquet"

SOURCE_KEY = "CORPORATIONS_CANADA"


# ============================================================
# HELPERS
# ============================================================

def load_metadata() -> dict:
    if not METADATA.exists():
        raise FileNotFoundError(
            f"Corporations Canada metadata not found: {METADATA}"
        )

    return json.loads(
        METADATA.read_text(encoding="utf-8")
    )


# ============================================================
# MAIN BUILD
# ============================================================

def main() -> None:
    print("=== V4 FEDERAL REGISTRY BUILD ===")
    print()

    # --------------------------------------------------------
    # Validate source files
    # --------------------------------------------------------

    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Corporations Canada source not found: {SOURCE}"
        )

    metadata = load_metadata()

    source_url = metadata.get("source_url")
    collected_at = metadata.get("collected_at_utc")
    source_last_modified = metadata.get("http_last_modified")
    source_sha256 = metadata.get("sha256")

    if not source_url:
        raise RuntimeError(
            "Metadata is missing source_url."
        )

    if not collected_at:
        raise RuntimeError(
            "Metadata is missing collected_at_utc."
        )

    if not source_sha256:
        raise RuntimeError(
            "Metadata is missing SHA-256 checksum."
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    verified_at = datetime.now(
        timezone.utc
    ).isoformat()

    # DuckDB CREATE VIEW does not support a prepared
    # parameter inside read_csv_auto(), therefore the local
    # path is safely escaped before embedding it in SQL.
    source_path = str(SOURCE).replace("'", "''")

    output_path = str(OUTPUT).replace("'", "''")

    con = duckdb.connect()

    try:

        # ----------------------------------------------------
        # Load official Corporations Canada CSV
        # ----------------------------------------------------

        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW federal_raw AS

            SELECT *

            FROM read_csv_auto(
                '{source_path}',
                header = true,
                all_varchar = true,
                sample_size = -1
            )
            """
        )

        # ----------------------------------------------------
        # Validate raw source
        # ----------------------------------------------------

        raw_count = con.execute(
            """
            SELECT COUNT(*)
            FROM federal_raw
            """
        ).fetchone()[0]

        duplicate_ids = con.execute(
            """
            SELECT COUNT(*)

            FROM (
                SELECT
                    "Corporation number"

                FROM federal_raw

                WHERE NULLIF(
                    TRIM("Corporation number"),
                    ''
                ) IS NOT NULL

                GROUP BY
                    "Corporation number"

                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

        blank_ids = con.execute(
            """
            SELECT COUNT(*)

            FROM federal_raw

            WHERE NULLIF(
                TRIM("Corporation number"),
                ''
            ) IS NULL
            """
        ).fetchone()[0]

        print(f"Raw records            : {raw_count:,}")
        print(f"Duplicate registry IDs : {duplicate_ids:,}")
        print(f"Blank registry IDs     : {blank_ids:,}")
        print()

        if raw_count == 0:
            raise RuntimeError(
                "Corporations Canada source contains zero records."
            )

        if duplicate_ids != 0:
            raise RuntimeError(
                "Duplicate corporation numbers detected. "
                "V4 Federal build cancelled."
            )

        if blank_ids != 0:
            raise RuntimeError(
                "Blank corporation numbers detected. "
                "V4 Federal build cancelled."
            )

        # ----------------------------------------------------
        # Build standardized V4 Federal registry layer
        #
        # IMPORTANT:
        # The source contains an Anniversary date.
        # We do NOT reinterpret that field as incorporation
        # date. Incorporation date remains NULL until supported
        # by appropriate official evidence.
        # ----------------------------------------------------

        con.execute(
            f"""
            COPY (

                SELECT

                    '{SOURCE_KEY}'
                        AS registry_source,

                    TRIM("Corporation number")
                        AS registry_id,

                    NULLIF(
                        TRIM("Business number (BN)"),
                        ''
                    )
                        AS business_number,

                    NULLIF(
                        TRIM("Corporate name - form 1"),
                        ''
                    )
                        AS legal_business_name,

                    NULLIF(
                        TRIM("Corporate name - form 2"),
                        ''
                    )
                        AS alternate_legal_name,

                    NULLIF(
                        TRIM("Governing legislation"),
                        ''
                    )
                        AS governing_legislation,

                    NULLIF(
                        TRIM("Status"),
                        ''
                    )
                        AS registration_status,

                    NULLIF(
                        TRIM("Status Detail"),
                        ''
                    )
                        AS registration_status_detail,

                    CAST(NULL AS DATE)
                        AS incorporation_date,

                    TRY_CAST(
                        NULLIF(
                            TRIM("Anniversary date"),
                            ''
                        )
                        AS DATE
                    )
                        AS anniversary_date,

                    TRY_CAST(
                        NULLIF(
                            TRIM(
                                "Year of last annual filing"
                            ),
                            ''
                        )
                        AS INTEGER
                    )
                        AS year_of_last_annual_filing,

                    TRY_CAST(
                        NULLIF(
                            TRIM(
                                "Date of last annual meeting"
                            ),
                            ''
                        )
                        AS DATE
                    )
                        AS date_of_last_annual_meeting,

                    NULLIF(
                        TRIM("Street"),
                        ''
                    )
                        AS registered_street,

                    NULLIF(
                        TRIM("Street 2"),
                        ''
                    )
                        AS registered_street_2,

                    NULLIF(
                        TRIM("City/town"),
                        ''
                    )
                        AS registered_city,

                    UPPER(
                        NULLIF(
                            TRIM("Province/territory"),
                            ''
                        )
                    )
                        AS registered_province,

                    UPPER(
                        NULLIF(
                            TRIM("Country"),
                            ''
                        )
                    )
                        AS registered_country,

                    UPPER(
                        REPLACE(
                            NULLIF(
                                TRIM("Postal code"),
                                ''
                            ),
                            ' ',
                            ''
                        )
                    )
                        AS registered_postal_code,

                    TRY_CAST(
                        NULLIF(
                            TRIM(
                                "Minimum number of directors"
                            ),
                            ''
                        )
                        AS INTEGER
                    )
                        AS minimum_directors,

                    TRY_CAST(
                        NULLIF(
                            TRIM(
                                "Maximum number of directors"
                            ),
                            ''
                        )
                        AS INTEGER
                    )
                        AS maximum_directors,

                    ?
                        AS source_url,

                    ?
                        AS source_collected_at,

                    ?
                        AS source_last_modified,

                    ?
                        AS source_sha256,

                    ?
                        AS last_verified_at,

                    'OFFICIAL_FEDERAL_REGISTRY'
                        AS evidence_type,

                    FALSE
                        AS incorporation_date_verified

                FROM federal_raw

            )
            TO '{output_path}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """,
            [
                source_url,
                collected_at,
                source_last_modified,
                source_sha256,
                verified_at,
            ],
        )

        # ----------------------------------------------------
        # Validate standardized output
        # ----------------------------------------------------

        stats = con.execute(
            """
            SELECT

                COUNT(*)
                    AS total,

                COUNT(*) FILTER (
                    WHERE legal_business_name IS NOT NULL
                )
                    AS with_legal_name,

                COUNT(*) FILTER (
                    WHERE registration_status IS NOT NULL
                )
                    AS with_status,

                COUNT(*) FILTER (
                    WHERE registered_province IS NOT NULL
                )
                    AS with_province,

                COUNT(*) FILTER (
                    WHERE registered_postal_code IS NOT NULL
                )
                    AS with_postal,

                COUNT(*) FILTER (
                    WHERE business_number IS NOT NULL
                )
                    AS with_bn,

                COUNT(*) FILTER (
                    WHERE incorporation_date IS NOT NULL
                )
                    AS with_incorporation_date,

                COUNT(*) FILTER (
                    WHERE source_url IS NOT NULL
                )
                    AS with_source,

                COUNT(*) FILTER (
                    WHERE last_verified_at IS NOT NULL
                )
                    AS with_verified_timestamp

            FROM read_parquet(?)
            """,
            [str(OUTPUT)],
        ).fetchone()

        output_duplicates = con.execute(
            """
            SELECT COUNT(*)

            FROM (
                SELECT
                    registry_id

                FROM read_parquet(?)

                GROUP BY registry_id

                HAVING COUNT(*) > 1
            )
            """,
            [str(OUTPUT)],
        ).fetchone()[0]

    finally:
        con.close()

    # --------------------------------------------------------
    # Final integrity checks
    # --------------------------------------------------------

    if stats[0] != raw_count:
        raise RuntimeError(
            "Output row count does not match raw source. "
            f"Raw={raw_count:,}, Output={stats[0]:,}"
        )

    if output_duplicates != 0:
        raise RuntimeError(
            "Duplicate registry IDs detected in V4 output."
        )

    if stats[1] == 0:
        raise RuntimeError(
            "No legal business names were produced."
        )

    if stats[2] == 0:
        raise RuntimeError(
            "No registration statuses were produced."
        )

    if stats[7] != stats[0]:
        raise RuntimeError(
            "Some records are missing source provenance."
        )

    if stats[8] != stats[0]:
        raise RuntimeError(
            "Some records are missing verification timestamps."
        )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    print("=== FEDERAL REGISTRY COVERAGE ===")
    print()

    print(f"Registry records       : {stats[0]:,}")
    print(f"Legal business names   : {stats[1]:,}")
    print(f"Registration status    : {stats[2]:,}")
    print(f"Province               : {stats[3]:,}")
    print(f"Postal code            : {stats[4]:,}")
    print(f"Business number        : {stats[5]:,}")
    print(f"Incorporation dates    : {stats[6]:,}")
    print(f"Source provenance      : {stats[7]:,}")
    print(f"Last verified timestamp: {stats[8]:,}")
    print(f"Duplicate output IDs   : {output_duplicates:,}")

    print()

    print(
        "NOTE: Anniversary date is preserved separately "
        "and is NOT treated as incorporation date."
    )

    print()

    print(f"Source URL             : {source_url}")
    print(f"Source collected       : {collected_at}")
    print(f"Source Last-Modified   : {source_last_modified}")
    print(f"Source SHA-256         : {source_sha256}")

    print()

    print(f"Output                  : {OUTPUT}")

    print()
    print("=== V4 FEDERAL REGISTRY SUCCESS ===")


if __name__ == "__main__":
    main()