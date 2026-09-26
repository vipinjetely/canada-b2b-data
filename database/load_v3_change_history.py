from __future__ import annotations

import os
from pathlib import Path

import duckdb
import psycopg
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]

CHANGE_FILE = (
    ROOT
    / "data"
    / "processed"
    / "v3"
    / "v3_daily_changes.parquet"
)

load_dotenv(ROOT / ".env")


TRACKED_FIELDS = [
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


def get_change_counts():
    con = duckdb.connect()

    try:
        result = con.execute(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE change_type = 'NEW'
                ),
                COUNT(*) FILTER (
                    WHERE change_type = 'CHANGED'
                ),
                COUNT(*) FILTER (
                    WHERE change_type = 'REMOVED'
                )
            FROM read_parquet(?)
            """,
            [str(CHANGE_FILE)],
        ).fetchone()

        return tuple(int(value) for value in result)

    finally:
        con.close()


def load_change_rows():
    con = duckdb.connect()

    try:
        rows = con.execute(
            """
            SELECT *
            FROM read_parquet(?)
            WHERE change_type IN (
                'NEW',
                'CHANGED',
                'REMOVED'
            )
            """,
            [str(CHANGE_FILE)],
        ).fetchall()

        columns = [
            item[0]
            for item in con.description
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    finally:
        con.close()


def normalize(value):
    if value is None:
        return None

    return str(value)


def already_exists(
    cursor,
    location_id,
    change_type,
    field_name,
    old_value,
    new_value,
    detected_at,
):
    cursor.execute(
        """
        SELECT 1
        FROM v3_location_change_history
        WHERE location_id = %s
          AND change_type = %s
          AND field_name IS NOT DISTINCT FROM %s
          AND old_value IS NOT DISTINCT FROM %s
          AND new_value IS NOT DISTINCT FROM %s
          AND detected_at = %s
        LIMIT 1
        """,
        (
            location_id,
            change_type,
            field_name,
            old_value,
            new_value,
            detected_at,
        ),
    )

    return cursor.fetchone() is not None


def insert_history(
    cursor,
    location_id,
    change_type,
    field_name,
    old_value,
    new_value,
    detected_at,
):
    if already_exists(
        cursor,
        location_id,
        change_type,
        field_name,
        old_value,
        new_value,
        detected_at,
    ):
        return False

    cursor.execute(
        """
        INSERT INTO v3_location_change_history (
            location_id,
            change_type,
            field_name,
            old_value,
            new_value,
            detected_at,
            source_name
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            location_id,
            change_type,
            field_name,
            old_value,
            new_value,
            detected_at,
            "V3 Daily Change Detection",
        ),
    )

    return True


def persist_changes(rows):
    connection = postgres_connection()

    inserted = 0

    try:
        with connection.cursor() as cursor:

            for row in rows:
                location_id = row["location_id"]
                change_type = row["change_type"]
                detected_at = row["detected_at"]

                if change_type == "NEW":
                    if insert_history(
                        cursor,
                        location_id,
                        "NEW",
                        None,
                        None,
                        normalize(row.get("business_name")),
                        detected_at,
                    ):
                        inserted += 1

                elif change_type == "REMOVED":
                    if insert_history(
                        cursor,
                        location_id,
                        "REMOVED",
                        None,
                        normalize(row.get("business_name")),
                        None,
                        detected_at,
                    ):
                        inserted += 1

                elif change_type == "CHANGED":
                    # The daily change file contains the new
                    # snapshot. Old values are read from the
                    # current PostgreSQL snapshot before reload.

                    cursor.execute(
                        """
                        SELECT
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
                        WHERE location_id = %s
                        """,
                        (location_id,),
                    )

                    old_row = cursor.fetchone()

                    if old_row is None:
                        raise RuntimeError(
                            "CHANGED location missing from "
                            f"current database: {location_id}"
                        )

                    old_values = dict(
                        zip(TRACKED_FIELDS, old_row)
                    )

                    for field in TRACKED_FIELDS:
                        old_value = normalize(
                            old_values.get(field)
                        )

                        new_value = normalize(
                            row.get(field)
                        )

                        if old_value == new_value:
                            continue

                        if insert_history(
                            cursor,
                            location_id,
                            "CHANGED",
                            field,
                            old_value,
                            new_value,
                            detected_at,
                        ):
                            inserted += 1

        connection.commit()

        return inserted

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def main() -> int:
    print("=== V3 CHANGE HISTORY LOAD ===")

    if not CHANGE_FILE.exists():
        raise FileNotFoundError(
            f"Change file not found: {CHANGE_FILE}"
        )

    new_count, changed_count, removed_count = (
        get_change_counts()
    )

    actionable = (
        new_count
        + changed_count
        + removed_count
    )

    print(f"NEW     : {new_count:,}")
    print(f"CHANGED : {changed_count:,}")
    print(f"REMOVED : {removed_count:,}")
    print(f"TO SAVE : {actionable:,}")

    if actionable == 0:
        print()
        print(
            "No NEW / CHANGED / REMOVED records "
            "to persist."
        )
        print("=== V3 CHANGE HISTORY SUCCESS ===")
        return 0

    rows = load_change_rows()

    inserted = persist_changes(rows)

    print()
    print("=== V3 CHANGE HISTORY SUCCESS ===")
    print(f"Actionable records : {len(rows):,}")
    print(f"History rows added : {inserted:,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())