from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json

import pandas as pd
import psycopg
from dotenv import load_dotenv
import os


INPUT_PATH = Path(
    "data/processed/v2/corporations_canada_normalized.csv"
)
METADATA_PATH = Path(
    "data/raw/v2/corporations_canada_metadata.json"
)

SOURCE_KEY = "corporations_canada"


def clean(value):
    """Convert pandas missing values to PostgreSQL NULL."""
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def parse_date(value):
    value = clean(value)

    if not value:
        return None

    parsed = pd.to_datetime(value, errors="coerce")

    if pd.isna(parsed):
        return None

    return parsed.date()


def get_connection():
    load_dotenv()

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def load_v2() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"Normalized dataset not found: {INPUT_PATH}"
        )

    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Metadata not found: {METADATA_PATH}"
        )

    metadata = json.loads(
        METADATA_PATH.read_text(encoding="utf-8")
    )

    collected_at = datetime.fromisoformat(
        metadata["collected_at_utc"]
    )

    source_updated_raw = metadata.get("http_last_modified")

    source_updated_at = (
        parsedate_to_datetime(source_updated_raw)
        if source_updated_raw
        else None
    )

    print("Reading normalized V2 dataset...")

    df = pd.read_csv(
        INPUT_PATH,
        dtype="string",
        low_memory=False,
    )

    total_rows = len(df)

    print(f"Rows ready for loading: {total_rows:,}")

    conn = get_connection()

    pipeline_run_id = None

    try:
        with conn.transaction():

            with conn.cursor() as cur:

                # -------------------------------------------------
                # Register pipeline run
                # -------------------------------------------------
                cur.execute(
                    """
                    INSERT INTO pipeline_runs (
                        status,
                        records_collected
                    )
                    VALUES ('running', %s)
                    RETURNING id
                    """,
                    (total_rows,),
                )

                pipeline_run_id = cur.fetchone()[0]

                # -------------------------------------------------
                # Resolve source
                # -------------------------------------------------
                cur.execute(
                    """
                    SELECT id
                    FROM data_sources
                    WHERE source_key = %s
                    """,
                    (SOURCE_KEY,),
                )

                row = cur.fetchone()

                if not row:
                    raise RuntimeError(
                        f"Source not registered: {SOURCE_KEY}"
                    )

                source_id = row[0]

                # -------------------------------------------------
                # Safety: prevent accidental duplicate federal load
                # -------------------------------------------------
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM business_source_records
                    WHERE source_id = %s
                    """,
                    (source_id,),
                )

                existing_source_rows = cur.fetchone()[0]

                if existing_source_rows:
                    raise RuntimeError(
                        "Corporations Canada V2 records already exist. "
                        "Refusing duplicate initial load."
                    )

                # -------------------------------------------------
                # Temporary staging table
                # -------------------------------------------------
                cur.execute(
                    """
                    CREATE TEMP TABLE federal_v2_stage (
                        federal_corporation_number TEXT,
                        business_number TEXT,
                        legal_name TEXT,
                        operating_name TEXT,
                        status TEXT,
                        street TEXT,
                        street_2 TEXT,
                        city TEXT,
                        province TEXT,
                        country TEXT,
                        postal_code TEXT,
                        source_record_id TEXT
                    ) ON COMMIT DROP
                    """
                )

                print("Bulk copying records into staging table...")

                with cur.copy(
                    """
                    COPY federal_v2_stage (
                        federal_corporation_number,
                        business_number,
                        legal_name,
                        operating_name,
                        status,
                        street,
                        street_2,
                        city,
                        province,
                        country,
                        postal_code,
                        source_record_id
                    )
                    FROM STDIN
                    """
                ) as copy:

                    for row in df.itertuples(index=False):

                        copy.write_row(
                            (
                                clean(
                                    row.federal_corporation_number
                                ),
                                clean(row.business_number),
                                clean(row.legal_name),
                                clean(row.operating_name),
                                clean(row.status),
                                clean(row.street),
                                clean(row.street_2),
                                clean(row.city),
                                clean(row.province),
                                clean(row.country),
                                clean(row.postal_code),
                                clean(row.source_record_id),
                            )
                        )

                # -------------------------------------------------
                # Insert canonical business entities
                # -------------------------------------------------
                print("Creating canonical business entities...")

                cur.execute(
                    """
                    INSERT INTO business_entities (
                        legal_name,
                        operating_name,
                        federal_corporation_number,
                        business_number,
                        registry_jurisdiction,
                        status,
                        street,
                        street_2,
                        city,
                        province,
                        country,
                        postal_code,
                        first_seen_at,
                        last_seen_at,
                        last_verified_at
                    )
                    SELECT
                        legal_name,
                        operating_name,
                        federal_corporation_number,
                        business_number,
                        'Federal',
                        status,
                        street,
                        street_2,
                        city,
                        province,
                        COALESCE(country, 'CA'),
                        postal_code,
                        %s,
                        %s,
                        %s
                    FROM federal_v2_stage
                    """,
                    (
                        collected_at,
                        collected_at,
                        collected_at,
                    ),
                )

                inserted_entities = cur.rowcount

                # -------------------------------------------------
                # Link source records to canonical entities
                # -------------------------------------------------
                print("Creating source-record provenance links...")

                cur.execute(
                    """
                    INSERT INTO business_source_records (
                        business_id,
                        source_id,
                        source_record_id,
                        source_business_name,
                        source_status,
                        source_updated_at,
                        collected_at,
                        last_verified_at
                    )
                    SELECT
                        b.id,
                        %s,
                        s.source_record_id,
                        s.legal_name,
                        s.status,
                        %s,
                        %s,
                        %s
                    FROM federal_v2_stage s
                    JOIN business_entities b
                      ON b.federal_corporation_number =
                         s.federal_corporation_number
                    """,
                    (
                        source_id,
                        source_updated_at,
                        collected_at,
                        collected_at,
                    ),
                )

                inserted_source_records = cur.rowcount

                if inserted_entities != total_rows:
                    raise RuntimeError(
                        "Entity count mismatch: "
                        f"expected {total_rows}, "
                        f"inserted {inserted_entities}"
                    )

                if inserted_source_records != total_rows:
                    raise RuntimeError(
                        "Source-record count mismatch: "
                        f"expected {total_rows}, "
                        f"inserted {inserted_source_records}"
                    )

                # -------------------------------------------------
                # Update source freshness
                # -------------------------------------------------
                cur.execute(
                    """
                    UPDATE data_sources
                    SET
                        last_source_update_at = %s,
                        last_collected_at = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        source_updated_at,
                        collected_at,
                        source_id,
                    ),
                )

                # -------------------------------------------------
                # Finish pipeline metrics
                # -------------------------------------------------
                cur.execute(
                    """
                    UPDATE pipeline_runs
                    SET
                        finished_at = NOW(),
                        status = 'completed',
                        records_inserted = %s
                    WHERE id = %s
                    """,
                    (
                        inserted_entities,
                        pipeline_run_id,
                    ),
                )

        print("V2 federal load completed successfully.")
        print(f"Business entities: {inserted_entities:,}")
        print(
            f"Source records: {inserted_source_records:,}"
        )
        print(f"Pipeline run ID: {pipeline_run_id}")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    load_v2()