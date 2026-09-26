from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import duckdb
import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent

SOURCE = (
    ROOT
    / "data"
    / "processed"
    / "v3"
    / "business_locations_enriched.parquet"
)

OUTPUT_DIR = ROOT / "data" / "processed" / "v3"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHANGE_FILE = OUTPUT_DIR / "v3_daily_changes.parquet"
SNAPSHOT_CSV = OUTPUT_DIR / "_v3_existing_snapshot.csv"

load_dotenv(ROOT / ".env")


COMPARE_FIELDS = [
    "business_name",
    "street",
    "city",
    "province",
    "postal_code",
    "phone",
    "email",
    "website",
    "basic_category",
    "operating_status",
    "employee_count",
    "employee_size_bucket",
    "employee_count_type",
]


def postgres_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def export_existing_snapshot() -> int:
    """
    Bulk-export the current PostgreSQL snapshot to CSV.

    This avoids fetching 1M+ rows into Python and inserting
    them into DuckDB row-by-row.
    """

    copy_sql = """
        COPY (
            SELECT
                location_id,
                business_name,
                street,
                city,
                province,
                postal_code,
                phone,
                email,
                website,
                basic_category,
                operating_status,
                employee_count,
                employee_size_bucket,
                employee_count_type
            FROM v3_business_locations
        )
        TO STDOUT
        WITH (
            FORMAT CSV,
            HEADER TRUE,
            NULL ''
        );
    """

    connection = postgres_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM v3_business_locations
                """
            )

            count = int(cursor.fetchone()[0])

            with SNAPSHOT_CSV.open("wb") as output:
                with cursor.copy(copy_sql) as copy:
                    for chunk in copy:
                        output.write(chunk)

        return count

    finally:
        connection.close()


def build_change_file(
    con: duckdb.DuckDBPyConnection,
) -> tuple[int, int, int, int]:

    source_path = str(SOURCE).replace("'", "''")
    snapshot_path = str(SNAPSHOT_CSV).replace("'", "''")
    output_path = str(CHANGE_FILE).replace("'", "''")

    comparisons = []

    for field in COMPARE_FIELDS:
        comparisons.append(
            f"""
            COALESCE(CAST(n.{field} AS VARCHAR), '')
            IS DISTINCT FROM
            COALESCE(CAST(o.{field} AS VARCHAR), '')
            """
        )

    changed_condition = " OR ".join(comparisons)

    con.execute(
        f"""
        COPY (
            WITH new_snapshot AS (
                SELECT
                    location_id,
                    business_name,
                    address AS street,
                    city,
                    province,
                    postal_code,
                    phone,
                    email,
                    website,
                    basic_category,
                    operating_status,
                    employee_count,
                    employee_size_bucket,
                    employee_count_type
                FROM read_parquet('{source_path}')
            ),

            existing_snapshot AS (
                SELECT
                    location_id,
                    business_name,
                    street,
                    city,
                    province,
                    postal_code,
                    phone,
                    email,
                    website,
                    basic_category,
                    operating_status,
                    TRY_CAST(employee_count AS BIGINT)
                        AS employee_count,
                    employee_size_bucket,
                    employee_count_type
                FROM read_csv_auto(
                    '{snapshot_path}',
                    HEADER = TRUE,
                    ALL_VARCHAR = TRUE,
                    NULLSTR = ''
                )
            ),

            current_changes AS (
                SELECT
                    n.location_id,

                    CASE
                        WHEN o.location_id IS NULL
                            THEN 'NEW'

                        WHEN {changed_condition}
                            THEN 'CHANGED'

                        ELSE 'UNCHANGED'
                    END AS change_type,

                    n.business_name,
                    n.street,
                    n.city,
                    n.province,
                    n.postal_code,
                    n.phone,
                    n.email,
                    n.website,
                    n.basic_category,
                    n.operating_status,
                    n.employee_count,
                    n.employee_size_bucket,
                    n.employee_count_type,

                    CURRENT_TIMESTAMP AS detected_at

                FROM new_snapshot n

                LEFT JOIN existing_snapshot o
                    ON n.location_id = o.location_id
            ),

            removed_records AS (
                SELECT
                    o.location_id,
                    'REMOVED' AS change_type,
                    o.business_name,
                    o.street,
                    o.city,
                    o.province,
                    o.postal_code,
                    o.phone,
                    o.email,
                    o.website,
                    o.basic_category,
                    o.operating_status,
                    o.employee_count,
                    o.employee_size_bucket,
                    o.employee_count_type,
                    CURRENT_TIMESTAMP AS detected_at

                FROM existing_snapshot o

                LEFT JOIN new_snapshot n
                    ON o.location_id = n.location_id

                WHERE n.location_id IS NULL
            )

            SELECT * FROM current_changes

            UNION ALL

            SELECT * FROM removed_records
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
            COUNT(*) FILTER (
                WHERE change_type = 'NEW'
            ),

            COUNT(*) FILTER (
                WHERE change_type = 'CHANGED'
            ),

            COUNT(*) FILTER (
                WHERE change_type = 'UNCHANGED'
            ),

            COUNT(*) FILTER (
                WHERE change_type = 'REMOVED'
            )

        FROM read_parquet('{output_path}')
        """
    ).fetchone()

    return tuple(int(value) for value in result)


def main() -> int:
    print("=== V3 DAILY CHANGE DETECTION ===")

    if not SOURCE.exists():
        raise FileNotFoundError(
            f"V3 source file not found: {SOURCE}"
        )

    if CHANGE_FILE.exists():
        CHANGE_FILE.unlink()

    if SNAPSHOT_CSV.exists():
        SNAPSHOT_CSV.unlink()

    try:
        print("Exporting PostgreSQL snapshot...")

        existing_count = export_existing_snapshot()

        print(
            f"Existing PostgreSQL snapshot: "
            f"{existing_count:,}"
        )

        con = duckdb.connect()

        try:
            (
                new_count,
                changed_count,
                unchanged_count,
                removed_count,
            ) = build_change_file(con)

        finally:
            con.close()

        total = (
            new_count
            + changed_count
            + unchanged_count
            + removed_count
        )

        print()
        print("=== CHANGE DETECTION SUCCESS ===")
        print(f"NEW       : {new_count:,}")
        print(f"CHANGED   : {changed_count:,}")
        print(f"UNCHANGED : {unchanged_count:,}")
        print(f"REMOVED   : {removed_count:,}")
        print(f"OUTPUT    : {total:,}")
        print(f"FILE      : {CHANGE_FILE}")
        print(
            "Detected at:",
            datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
        )

        return 0

    finally:
        if SNAPSHOT_CSV.exists():
            SNAPSHOT_CSV.unlink()
            print("Temporary PostgreSQL snapshot removed.")


if __name__ == "__main__":
    raise SystemExit(main())