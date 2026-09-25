from pathlib import Path
from datetime import datetime
import json
import os

import pandas as pd
import psycopg
from dotenv import load_dotenv


ENTITY_PATH = Path(
    "data/processed/v2/entity_resolution/"
    "vancouver_local_entities_validated.csv"
)

MEMBERS_PATH = Path(
    "data/processed/v2/entity_resolution/"
    "vancouver_entity_members.csv"
)

METADATA_PATH = Path(
    "data/raw/v2/vancouver_business_licences_metadata.json"
)

SOURCE_KEY = "vancouver_business_licences"


def clean(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    return value or None


def clean_int(value):
    if pd.isna(value):
        return None

    try:
        return int(float(str(value)))
    except (ValueError, TypeError):
        return None


def clean_float(value):
    if pd.isna(value):
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def clean_bool(value):
    if pd.isna(value):
        return False

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
    }


def parse_timestamp(value):
    value = clean(value)

    if not value:
        return None

    parsed = pd.to_datetime(
        value,
        errors="coerce",
        utc=True,
    )

    if pd.isna(parsed):
        return None

    return parsed.to_pydatetime()


def get_connection():
    load_dotenv()

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def main():
    if not ENTITY_PATH.exists():
        raise FileNotFoundError(ENTITY_PATH)

    if not MEMBERS_PATH.exists():
        raise FileNotFoundError(MEMBERS_PATH)

    if not METADATA_PATH.exists():
        raise FileNotFoundError(METADATA_PATH)

    metadata = json.loads(
        METADATA_PATH.read_text(
            encoding="utf-8"
        )
    )

    collected_at = datetime.fromisoformat(
        metadata["collected_at_utc"]
    )

    print("Reading validated Vancouver entities...")

    entities = pd.read_csv(
        ENTITY_PATH,
        dtype="string",
        low_memory=False,
    )

    members = pd.read_csv(
        MEMBERS_PATH,
        dtype="string",
        low_memory=False,
    )

    review_count = int(
        entities["identity_quality"]
        .eq("REVIEW_REQUIRED")
        .sum()
    )

    load_entities = entities[
        ~entities["identity_quality"].eq(
            "REVIEW_REQUIRED"
        )
    ].copy()

    valid_keys = set(
        load_entities["local_entity_key"]
    )

    load_members = members[
        members["local_entity_key"].isin(
            valid_keys
        )
    ].copy()

    print(
        f"Entities eligible: {len(load_entities):,}"
    )
    print(
        f"Review entities excluded: {review_count:,}"
    )
    print(
        f"Source records eligible: {len(load_members):,}"
    )

    conn = get_connection()

    pipeline_run_id = None

    try:
        with conn.transaction():
            with conn.cursor() as cur:

                # ----------------------------------
                # Safety checks
                # ----------------------------------

                cur.execute(
                    """
                    SELECT id
                    FROM data_sources
                    WHERE source_key = %s
                    """,
                    (SOURCE_KEY,),
                )

                source_row = cur.fetchone()

                if not source_row:
                    raise RuntimeError(
                        "Vancouver source is not registered."
                    )

                source_id = source_row[0]

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM business_source_records
                    WHERE source_id = %s
                    """,
                    (source_id,),
                )

                existing = cur.fetchone()[0]

                if existing:
                    raise RuntimeError(
                        "Vancouver source records already exist. "
                        "Refusing duplicate initial load."
                    )

                # ----------------------------------
                # Pipeline run
                # ----------------------------------

                cur.execute(
                    """
                    INSERT INTO pipeline_runs (
                        status,
                        records_collected
                    )
                    VALUES ('running', %s)
                    RETURNING id
                    """,
                    (len(load_members),),
                )

                pipeline_run_id = cur.fetchone()[0]

                # ----------------------------------
                # Temporary entity staging
                # ----------------------------------

                cur.execute(
                    """
                    CREATE TEMP TABLE vancouver_entity_stage (
                        local_entity_key TEXT PRIMARY KEY,
                        legal_name TEXT,
                        operating_name TEXT,
                        display_name TEXT,
                        street TEXT,
                        city TEXT,
                        province TEXT,
                        country TEXT,
                        postal_code TEXT,
                        business_type TEXT,
                        business_subtype TEXT,
                        employee_count INTEGER,
                        employee_size_bucket TEXT,
                        first_issued_at TIMESTAMPTZ,
                        latest_extract_at TIMESTAMPTZ,
                        identity_confidence_score NUMERIC,
                        quality_score NUMERIC,
                        is_new_1d BOOLEAN,
                        is_new_7d BOOLEAN,
                        is_new_30d BOOLEAN
                    ) ON COMMIT DROP
                    """
                )

                print(
                    "Copying canonical entities to staging..."
                )

                with cur.copy(
                    """
                    COPY vancouver_entity_stage (
                        local_entity_key,
                        legal_name,
                        operating_name,
                        display_name,
                        street,
                        city,
                        province,
                        country,
                        postal_code,
                        business_type,
                        business_subtype,
                        employee_count,
                        employee_size_bucket,
                        first_issued_at,
                        latest_extract_at,
                        identity_confidence_score,
                        quality_score,
                        is_new_1d,
                        is_new_7d,
                        is_new_30d
                    )
                    FROM STDIN
                    """
                ) as copy:

                    for row in load_entities.itertuples(
                        index=False
                    ):
                        copy.write_row(
                            (
                                clean(row.local_entity_key),
                                clean(row.legal_name)
                                or clean(row.display_name),
                                clean(row.operating_name),
                                clean(row.display_name),
                                clean(row.street),
                                clean(row.city),
                                clean(row.province),
                                clean(row.country) or "CA",
                                clean(row.postal_code),
                                clean(row.business_type),
                                clean(row.business_subtype),
                                clean_int(row.employee_count),
                                clean(row.employee_size_bucket),
                                parse_timestamp(
                                    row.first_issued_at
                                ),
                                parse_timestamp(
                                    row.latest_extract_at
                                ),
                                clean_float(
                                    row.identity_confidence_score
                                ),
                                clean_float(
                                    row.quality_score
                                ),
                                clean_bool(row.is_new_1d),
                                clean_bool(row.is_new_7d),
                                clean_bool(row.is_new_30d),
                            )
                        )

                # ----------------------------------
                # Insert canonical local entities
                # ----------------------------------

                print(
                    "Creating Vancouver business entities..."
                )

                cur.execute(
                    """
                    INSERT INTO business_entities (
                        legal_name,
                        operating_name,
                        province_registry_id,
                        registry_jurisdiction,
                        status,
                        street,
                        city,
                        province,
                        country,
                        postal_code,
                        industry,
                        employee_count,
                        employee_size_bucket,
                        first_seen_at,
                        last_seen_at,
                        last_verified_at,
                        quality_score,
                        confidence_score,
                        is_new_1d,
                        is_new_7d,
                        is_new_30d
                    )
                    SELECT
                        COALESCE(legal_name, display_name),
                        operating_name,
                        local_entity_key,
                        'Vancouver, BC',
                        'Issued',
                        street,
                        city,
                        province,
                        country,
                        postal_code,
                        CASE
                            WHEN business_subtype IS NOT NULL
                            THEN business_type || ' / ' ||
                                 business_subtype
                            ELSE business_type
                        END,
                        employee_count,
                        employee_size_bucket,
                        COALESCE(
                            first_issued_at,
                            %s
                        ),
                        COALESCE(
                            latest_extract_at,
                            %s
                        ),
                        COALESCE(
                            latest_extract_at,
                            %s
                        ),
                        quality_score,
                        identity_confidence_score,
                        is_new_1d,
                        is_new_7d,
                        is_new_30d
                    FROM vancouver_entity_stage
                    """,
                    (
                        collected_at,
                        collected_at,
                        collected_at,
                    ),
                )

                inserted_entities = cur.rowcount

                if inserted_entities != len(
                    load_entities
                ):
                    raise RuntimeError(
                        "Vancouver entity count mismatch."
                    )

                # ----------------------------------
                # Temporary member staging
                # ----------------------------------

                cur.execute(
                    """
                    CREATE TEMP TABLE vancouver_member_stage (
                        local_entity_key TEXT,
                        source_record_id TEXT,
                        licence_number TEXT,
                        licence_revision TEXT,
                        folder_year TEXT,
                        display_name TEXT,
                        business_type TEXT,
                        business_subtype TEXT,
                        employee_count TEXT,
                        issued_at TIMESTAMPTZ,
                        expired_at TIMESTAMPTZ,
                        extract_at TIMESTAMPTZ
                    ) ON COMMIT DROP
                    """
                )

                print(
                    "Copying Vancouver source records..."
                )

                with cur.copy(
                    """
                    COPY vancouver_member_stage (
                        local_entity_key,
                        source_record_id,
                        licence_number,
                        licence_revision,
                        folder_year,
                        display_name,
                        business_type,
                        business_subtype,
                        employee_count,
                        issued_at,
                        expired_at,
                        extract_at
                    )
                    FROM STDIN
                    """
                ) as copy:

                    for row in load_members.itertuples(
                        index=False
                    ):
                        copy.write_row(
                            (
                                clean(row.local_entity_key),
                                clean(row.source_record_id),
                                clean(row.LicenceNumber),
                                clean(
                                    row.LicenceRevisionNumber
                                ),
                                clean(row.FOLDERYEAR),
                                clean(row.display_name),
                                clean(row.BusinessType),
                                clean(row.BusinessSubType),
                                clean(row.employee_count),
                                parse_timestamp(row.issued_at),
                                parse_timestamp(row.expired_at),
                                parse_timestamp(row.extract_at),
                            )
                        )

                # ----------------------------------
                # Source provenance records
                # ----------------------------------

                print(
                    "Creating source-record provenance..."
                )

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
                        last_verified_at,
                        raw_record
                    )
                    SELECT
                        b.id,
                        %s,
                        m.source_record_id,
                        m.display_name,
                        'Issued',
                        m.extract_at,
                        %s,
                        m.extract_at,
                        jsonb_build_object(
                            'licence_number',
                                m.licence_number,
                            'licence_revision',
                                m.licence_revision,
                            'folder_year',
                                m.folder_year,
                            'business_type',
                                m.business_type,
                            'business_subtype',
                                m.business_subtype,
                            'employee_count',
                                m.employee_count,
                            'issued_at',
                                m.issued_at,
                            'expired_at',
                                m.expired_at
                        )
                    FROM vancouver_member_stage m
                    JOIN business_entities b
                      ON b.registry_jurisdiction =
                         'Vancouver, BC'
                     AND b.province_registry_id =
                         m.local_entity_key
                    """,
                    (
                        source_id,
                        collected_at,
                    ),
                )

                inserted_source_records = cur.rowcount

                if inserted_source_records != len(
                    load_members
                ):
                    raise RuntimeError(
                        "Vancouver source-record "
                        "count mismatch."
                    )

                # ----------------------------------
                # Update source registry
                # ----------------------------------

                cur.execute(
                    """
                    UPDATE data_sources
                    SET
                        last_source_update_at = (
                            SELECT MAX(extract_at)
                            FROM vancouver_member_stage
                        ),
                        last_collected_at = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        collected_at,
                        source_id,
                    ),
                )

                # ----------------------------------
                # Finish pipeline run
                # ----------------------------------

                cur.execute(
                    """
                    UPDATE pipeline_runs
                    SET
                        finished_at = NOW(),
                        status = 'completed',
                        records_inserted = %s,
                        records_deduplicated = %s,
                        records_failed = 0
                    WHERE id = %s
                    """,
                    (
                        inserted_entities,
                        len(load_members)
                        - inserted_entities,
                        pipeline_run_id,
                    ),
                )

        print(
            "\n=== VANCOUVER DATABASE LOAD ==="
        )

        print(
            f"Canonical entities inserted: "
            f"{inserted_entities:,}"
        )

        print(
            f"Source records inserted: "
            f"{inserted_source_records:,}"
        )

        print(
            f"Review entities excluded: "
            f"{review_count:,}"
        )

        print(
            f"Pipeline run ID: {pipeline_run_id}"
        )

        print(
            "\nVancouver V2 load completed successfully."
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()