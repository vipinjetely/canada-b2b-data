from __future__ import annotations

from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parent

SOURCE = (
    ROOT
    / "data"
    / "processed"
    / "v3"
    / "business_locations_enriched.parquet"
)

OUTPUT = (
    ROOT
    / "data"
    / "processed"
    / "v3"
    / "business_locations_scored.parquet"
)


def main() -> int:
    print("=== V3 BUSINESS QUALITY SCORING ===")

    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Source file not found: {SOURCE}"
        )

    source_path = str(SOURCE).replace("'", "''")
    output_path = str(OUTPUT).replace("'", "''")

    con = duckdb.connect()

    try:
        con.execute(
            f"""
            COPY (
                WITH scored AS (
                    SELECT
                        *,

                        LEAST(
                            100,

                            /* Core identity */
                            CASE
                                WHEN business_name IS NOT NULL
                                     AND TRIM(business_name) <> ''
                                THEN 15 ELSE 0
                            END

                            +

                            CASE
                                WHEN conservative_location_key
                                     IS NOT NULL
                                THEN 10 ELSE 0
                            END

                            +

                            /* Address evidence */
                            CASE
                                WHEN address IS NOT NULL
                                     AND city IS NOT NULL
                                     AND province IS NOT NULL
                                THEN 10 ELSE 0
                            END

                            +

                            CASE
                                WHEN postal_code IS NOT NULL
                                THEN 5 ELSE 0
                            END

                            +

                            /* Contactability */
                            CASE
                                WHEN phone IS NOT NULL
                                THEN 15 ELSE 0
                            END

                            +

                            CASE
                                WHEN email IS NOT NULL
                                THEN 15 ELSE 0
                            END

                            +

                            CASE
                                WHEN website IS NOT NULL
                                THEN 10 ELSE 0
                            END

                            +

                            /* Business classification */
                            CASE
                                WHEN basic_category IS NOT NULL
                                THEN 5 ELSE 0
                            END

                            +

                            /* Source confidence */
                            CASE
                                WHEN confidence >= 0.90 THEN 10
                                WHEN confidence >= 0.80 THEN 8
                                WHEN confidence >= 0.70 THEN 6
                                WHEN confidence >= 0.50 THEN 3
                                ELSE 0
                            END

                            +

                            /* Verified employee evidence only */
                            CASE
                                WHEN employee_count_type = 'VERIFIED'
                                     AND employee_evidence_scope = 'LOCATION'
                                THEN 5
                                ELSE 0
                            END

                        )::INTEGER AS quality_score

                    FROM read_parquet('{source_path}')
                ),

                classified AS (
                    SELECT
                        *,

                        CASE
                            WHEN quality_score >= 80
                                 AND phone IS NOT NULL
                                 AND (
                                     email IS NOT NULL
                                     OR website IS NOT NULL
                                 )
                            THEN 'SALES_READY'

                            WHEN quality_score >= 55
                            THEN 'PARTIAL'

                            ELSE 'INCOMPLETE'
                        END AS record_readiness,

                        CASE
                            WHEN confidence >= 0.90
                            THEN 'HIGH'

                            WHEN confidence >= 0.70
                            THEN 'MEDIUM'

                            ELSE 'LOW'
                        END AS source_confidence_band

                    FROM scored
                )

                SELECT *
                FROM classified
            )
            TO '{output_path}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        result = con.execute(
            f"""
            SELECT
                COUNT(*) AS total,

                COUNT(*) FILTER (
                    WHERE record_readiness = 'SALES_READY'
                ) AS sales_ready,

                COUNT(*) FILTER (
                    WHERE record_readiness = 'PARTIAL'
                ) AS partial,

                COUNT(*) FILTER (
                    WHERE record_readiness = 'INCOMPLETE'
                ) AS incomplete,

                ROUND(AVG(quality_score), 2)
                    AS average_quality,

                COUNT(*) FILTER (
                    WHERE source_confidence_band = 'HIGH'
                ) AS high_confidence

            FROM read_parquet('{output_path}')
            """
        ).fetchone()

        print(f"Total records   : {result[0]:,}")
        print(f"Sales-ready     : {result[1]:,}")
        print(f"Partial         : {result[2]:,}")
        print(f"Incomplete      : {result[3]:,}")
        print(f"Average quality : {result[4]}")
        print(f"High confidence : {result[5]:,}")
        print(f"Output          : {OUTPUT}")

        print()
        print("=== V3 QUALITY SCORING SUCCESS ===")

        return 0

    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())