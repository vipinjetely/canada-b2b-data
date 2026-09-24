import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv


load_dotenv()

INPUT_PATH = Path(
    "data/processed/corporations_canada_enriched.csv"
)

DB_COLUMNS = [
    "corporation_number",
    "business_number",
    "business_name",
    "business_name_alt",
    "governing_legislation",
    "status",
    "status_detail",
    "anniversary_date",
    "last_annual_filing_year",
    "last_annual_meeting_date",
    "street",
    "street_2",
    "city",
    "province",
    "country",
    "postal_code",
    "minimum_directors",
    "maximum_directors",
    "odbus_business_sector",
    "odbus_business_subsector",
    "odbus_business_description",
    "odbus_derived_naics",
    "odbus_source_naics_primary",
    "odbus_naics_description",
    "odbus_latitude",
    "odbus_longitude",
    "odbus_total_employees",
    "odbus_provider",
    "odbus_source_record_id",
    "odbus_matched",
    "source",
    "source_record_id",
    "collected_at_utc",
]


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def load_businesses() -> None:
    print("Reading enriched dataset...")

    df = pd.read_csv(
        INPUT_PATH,
        dtype=str,
        low_memory=False,
    )

    missing = set(DB_COLUMNS) - set(df.columns)

    if missing:
        raise ValueError(
            f"Required columns missing: {sorted(missing)}"
        )

    df = df[DB_COLUMNS].copy()

    # Statistics Canada ODBus uses ".." for unavailable values.
    df = df.replace("..", pd.NA)

    # Clean integer fields.
    integer_columns = [
        "last_annual_filing_year",
        "minimum_directors",
        "maximum_directors",
    ]

    for column in integer_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        ).astype("Int64")

    # Clean floating-point fields.
    float_columns = [
        "odbus_latitude",
        "odbus_longitude",
    ]

    for column in float_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # Normalize boolean field.
    df["odbus_matched"] = (
        df["odbus_matched"]
        .astype("string")
        .str.strip()
        .str.lower()
        .map(
            {
                "true": True,
                "false": False,
                "1": True,
                "0": False,
            }
        )
        .fillna(False)
    )

    # Convert pandas missing values to Python None
    # so PostgreSQL COPY receives NULL values.
    df = df.astype(object).where(
        pd.notna(df),
        None,
    )

    print(f"Rows ready for loading: {len(df):,}")

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            print("Clearing existing business records...")

            cursor.execute(
                "TRUNCATE TABLE businesses RESTART IDENTITY;"
            )

            columns_sql = ", ".join(DB_COLUMNS)

            copy_sql = (
                f"COPY businesses ({columns_sql}) "
                "FROM STDIN"
            )

            print("Bulk loading into PostgreSQL...")

            with cursor.copy(copy_sql) as copy:
                for row in df.itertuples(
                    index=False,
                    name=None,
                ):
                    copy.write_row(row)

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    print("DATABASE LOAD COMPLETE")


if __name__ == "__main__":
    load_businesses()