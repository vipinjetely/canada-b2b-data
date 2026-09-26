import os
from pathlib import Path

import duckdb
import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]

SOURCE = (
    ROOT
    / "data"
    / "processed"
    / "v3"
    / "business_locations_scored.parquet"
)

TEMP_CSV = (
    ROOT
    / "data"
    / "processed"
    / "v3"
    / "_v3_postgres_load.csv"
)

load_dotenv(ROOT / ".env")


def postgres_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def validate_source():
    con = duckdb.connect()

    try:
        return con.execute(
            """
            SELECT
                COUNT(*) AS total,

                COUNT(DISTINCT location_id)
                    AS unique_ids,

                COUNT(*) FILTER (
                    WHERE employee_count_type = 'VERIFIED'
                ) AS verified_employee,

                COUNT(*) FILTER (
                    WHERE employee_count_type = 'UNKNOWN'
                ) AS unknown_employee,

                COUNT(*) FILTER (
                    WHERE record_readiness = 'SALES_READY'
                ) AS sales_ready,

                COUNT(*) FILTER (
                    WHERE record_readiness = 'PARTIAL'
                ) AS partial,

                COUNT(*) FILTER (
                    WHERE record_readiness = 'INCOMPLETE'
                ) AS incomplete,

                COUNT(*) FILTER (
                    WHERE source_confidence_band = 'HIGH'
                ) AS high_confidence

            FROM read_parquet(?)
            """,
            [str(SOURCE)],
        ).fetchone()

    finally:
        con.close()


def export_csv():
    con = duckdb.connect()

    source_path = str(SOURCE).replace("'", "''")
    temp_path = str(TEMP_CSV).replace("'", "''")

    try:
        con.execute(
            f"""
            COPY (
                SELECT
                    location_id,
                    business_name,
                    normalized_name,

                    address AS street,
                    city,
                    province,
                    postal_code,
                    country,

                    basic_category,

                    phone,
                    email,
                    website,
                    website_domain,

                    operating_status,

                    confidence AS source_confidence,

                    conservative_location_key,
                    resolution_method,

                    employee_count,
                    employee_size_bucket,
                    employee_count_type,

                    employee_evidence_source,
                    employee_evidence_url,
                    employee_evidence_scope,
                    employee_verified_at,

                    quality_score,
                    record_readiness,
                    source_confidence_band

                FROM read_parquet('{source_path}')
            )
            TO '{temp_path}'
            (
                FORMAT CSV,
                HEADER TRUE,
                NULL ''
            )
            """
        )

    finally:
        con.close()


def load_postgres(expected):
    connection = postgres_connection()

    try:
        with connection.cursor() as cursor:

            # Refresh only current-state V3 tables.
            #
            # IMPORTANT:
            # v3_location_change_history is intentionally
            # preserved across refreshes.
            cursor.execute(
                """
                TRUNCATE TABLE
                    v3_contact_evidence,
                    v3_employee_evidence,
                    v3_location_sources,
                    v3_business_locations
                RESTART IDENTITY CASCADE;
                """
            )

            copy_sql = """
                COPY v3_business_locations (
                    location_id,
                    business_name,
                    normalized_name,
                    street,
                    city,
                    province,
                    postal_code,
                    country,
                    basic_category,
                    phone,
                    email,
                    website,
                    website_domain,
                    operating_status,
                    source_confidence,
                    conservative_location_key,
                    resolution_method,
                    employee_count,
                    employee_size_bucket,
                    employee_count_type,
                    employee_evidence_source,
                    employee_evidence_url,
                    employee_evidence_scope,
                    employee_verified_at,
                    quality_score,
                    record_readiness,
                    source_confidence_band
                )
                FROM STDIN
                WITH (
                    FORMAT CSV,
                    HEADER TRUE,
                    NULL ''
                );
            """

            with cursor.copy(copy_sql) as copy:
                with TEMP_CSV.open("rb") as source:
                    while True:
                        chunk = source.read(1024 * 1024)

                        if not chunk:
                            break

                        copy.write(chunk)

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,

                    COUNT(*) FILTER (
                        WHERE phone IS NOT NULL
                    ) AS with_phone,

                    COUNT(*) FILTER (
                        WHERE email IS NOT NULL
                    ) AS with_email,

                    COUNT(*) FILTER (
                        WHERE website IS NOT NULL
                    ) AS with_website,

                    COUNT(*) FILTER (
                        WHERE employee_count_type = 'VERIFIED'
                    ) AS verified_employee,

                    COUNT(*) FILTER (
                        WHERE employee_count_type = 'UNKNOWN'
                    ) AS unknown_employee,

                    COUNT(*) FILTER (
                        WHERE record_readiness = 'SALES_READY'
                    ) AS sales_ready,

                    COUNT(*) FILTER (
                        WHERE record_readiness = 'PARTIAL'
                    ) AS partial,

                    COUNT(*) FILTER (
                        WHERE record_readiness = 'INCOMPLETE'
                    ) AS incomplete,

                    COUNT(*) FILTER (
                        WHERE source_confidence_band = 'HIGH'
                    ) AS high_confidence

                FROM v3_business_locations;
                """
            )

            result = cursor.fetchone()

            # Validate BEFORE commit so a mismatch rolls back
            # the entire refresh.
            if result[0] != expected[0]:
                raise RuntimeError(
                    "PostgreSQL row count does not match "
                    "source row count."
                )

            if result[4] != expected[2]:
                raise RuntimeError(
                    "Verified employee count mismatch."
                )

            if result[5] != expected[3]:
                raise RuntimeError(
                    "Unknown employee count mismatch."
                )

            if result[6] != expected[4]:
                raise RuntimeError(
                    "Sales-ready count mismatch."
                )

            if result[7] != expected[5]:
                raise RuntimeError(
                    "Partial count mismatch."
                )

            if result[8] != expected[6]:
                raise RuntimeError(
                    "Incomplete count mismatch."
                )

            if result[9] != expected[7]:
                raise RuntimeError(
                    "High-confidence count mismatch."
                )

        connection.commit()

        return result

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def main():
    print("=== V3 POSTGRESQL LOAD ===")

    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Source parquet not found: {SOURCE}"
        )

    source_stats = validate_source()

    print(f"Source rows: {source_stats[0]:,}")
    print(f"Unique location IDs: {source_stats[1]:,}")
    print(f"Verified employee: {source_stats[2]:,}")
    print(f"Unknown employee: {source_stats[3]:,}")
    print(f"Sales-ready: {source_stats[4]:,}")
    print(f"Partial: {source_stats[5]:,}")
    print(f"Incomplete: {source_stats[6]:,}")
    print(f"High confidence: {source_stats[7]:,}")

    if source_stats[0] != source_stats[1]:
        raise RuntimeError(
            "Duplicate location_id detected. "
            "Database load cancelled."
        )

    if (
        source_stats[4]
        + source_stats[5]
        + source_stats[6]
        != source_stats[0]
    ):
        raise RuntimeError(
            "Readiness classifications do not cover "
            "all source records."
        )

    print("Source validation: PASS")

    if TEMP_CSV.exists():
        TEMP_CSV.unlink()

    try:
        print("Preparing bulk-load file...")
        export_csv()

        print("Loading PostgreSQL...")
        loaded = load_postgres(source_stats)

        print()
        print("=== V3 POSTGRESQL LOAD SUCCESS ===")
        print(f"Locations: {loaded[0]:,}")
        print(f"With phone: {loaded[1]:,}")
        print(f"With email: {loaded[2]:,}")
        print(f"With website: {loaded[3]:,}")
        print(f"Verified employee: {loaded[4]:,}")
        print(f"Unknown employee: {loaded[5]:,}")
        print(f"Sales-ready: {loaded[6]:,}")
        print(f"Partial: {loaded[7]:,}")
        print(f"Incomplete: {loaded[8]:,}")
        print(f"High confidence: {loaded[9]:,}")

    finally:
        if TEMP_CSV.exists():
            TEMP_CSV.unlink()
            print("Temporary CSV removed.")


if __name__ == "__main__":
    main()