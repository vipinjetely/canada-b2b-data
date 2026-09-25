from pathlib import Path
from datetime import datetime
import json
import os

import pandas as pd
import psycopg
from dotenv import load_dotenv


ENTITIES_PATH = Path(
    "data/processed/v2/entity_resolution/"
    "toronto_local_entities.csv"
)

MEMBERS_PATH = Path(
    "data/processed/v2/entity_resolution/"
    "toronto_entity_members.csv"
)

MATCHES_PATH = Path(
    "data/processed/v2/entity_resolution/"
    "toronto_federal_matches.csv"
)

METADATA_PATH = Path(
    "data/raw/v2/"
    "toronto_business_licences_metadata.json"
)

SOURCE_KEY = "toronto_business_licences"

STRONG_MATCHES = {
    "FEDERAL_NAME_POSTAL_ADDRESS",
    "FEDERAL_NAME_POSTAL_CITY",
    "FEDERAL_NAME_POSTAL",
}


def clean(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value or value.lower() in {
        "nan",
        "none",
        "<na>",
    }:
        return None

    return value


def clean_float(value):
    value = clean(value)

    if value is None:
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def clean_bool(value):
    value = clean(value)

    if value is None:
        return False

    return value.lower() in {
        "true",
        "1",
        "yes",
        "t",
    }


def parse_timestamp(value):
    value = clean(value)

    if value is None:
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
    print("Reading Toronto entity-resolution outputs...")

    entities = pd.read_csv(
        ENTITIES_PATH,
        dtype="string",
        low_memory=False,
    )

    members = pd.read_csv(
        MEMBERS_PATH,
        dtype="string",
        low_memory=False,
    )

    matches = pd.read_csv(
        MATCHES_PATH,
        dtype="string",
        low_memory=False,
    )

    metadata = json.loads(
        METADATA_PATH.read_text(
            encoding="utf-8"
        )
    )

    collected_at = datetime.fromisoformat(
        metadata["collected_at_utc"]
    )

    strong = matches[
        matches[
            "federal_match_category"
        ].isin(STRONG_MATCHES)
    ].copy()

    print(
        f"Local canonical entities: {len(entities):,}"
    )
    print(
        f"Local source records: {len(members):,}"
    )
    print(
        f"Strong federal matches: {len(strong):,}"
    )

    # Every current Toronto licence must either be
    # represented by a local candidate or strong match.
    expected_source_records = (
        len(members) + len(strong)
    )

    if expected_source_records != len(matches):
        raise RuntimeError(
            "Toronto resolution does not account for "
            "every licence record. "
            f"Members={len(members):,}, "
            f"strong={len(strong):,}, "
            f"total={len(matches):,}."
        )

    conn = get_connection()

    try:
        with conn.transaction():
            with conn.cursor() as cur:

                # ---------------------------------
                # Source registry
                # ---------------------------------

                cur.execute(
                    """
                    SELECT id
                    FROM data_sources
                    WHERE source_key = %s
                    """,
                    (SOURCE_KEY,),
                )

                row = cur.fetchone()

                if row is None:
                    raise RuntimeError(
                        "Toronto source not registered."
                    )

                source_id = row[0]

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
                        "Toronto source records already "
                        "exist. Refusing duplicate load."
                    )

                # ---------------------------------
                # Pipeline run
                # ---------------------------------

                cur.execute(
                    """
                    INSERT INTO pipeline_runs (
                        status,
                        records_collected
                    )
                    VALUES ('running', %s)
                    RETURNING id
                    """,
                    (len(matches),),
                )

                pipeline_run_id = cur.fetchone()[0]

                # ---------------------------------
                # Local entity staging
                # ---------------------------------

                cur.execute(
                    """
                    CREATE TEMP TABLE toronto_entity_stage (
                        local_entity_key TEXT PRIMARY KEY,
                        legal_name TEXT NOT NULL,
                        operating_name TEXT,
                        street TEXT,
                        city TEXT,
                        province TEXT,
                        country TEXT,
                        postal_code TEXT,
                        phone TEXT,
                        industry TEXT,
                        first_issued_at TIMESTAMPTZ,
                        latest_source_update_at TIMESTAMPTZ,
                        quality_score NUMERIC,
                        confidence_score NUMERIC,
                        is_new_1d BOOLEAN,
                        is_new_7d BOOLEAN,
                        is_new_30d BOOLEAN
                    ) ON COMMIT DROP
                    """
                )

                print(
                    "Copying Toronto canonical entities..."
                )

                with cur.copy(
                    """
                    COPY toronto_entity_stage (
                        local_entity_key,
                        legal_name,
                        operating_name,
                        street,
                        city,
                        province,
                        country,
                        postal_code,
                        phone,
                        industry,
                        first_issued_at,
                        latest_source_update_at,
                        quality_score,
                        confidence_score,
                        is_new_1d,
                        is_new_7d,
                        is_new_30d
                    )
                    FROM STDIN
                    """
                ) as copy:

                    for row in entities.itertuples(
                        index=False
                    ):
                        copy.write_row(
                            (
                                clean(row.local_entity_key),
                                clean(row.legal_name)
                                or clean(row.display_name),
                                clean(row.operating_name),
                                clean(row.street),
                                clean(row.city),
                                clean(row.province),
                                clean(row.country) or "CA",
                                clean(row.postal_code),
                                clean(row.phone),
                                clean(row.industry),
                                parse_timestamp(
                                    row.first_issued_at
                                ),
                                parse_timestamp(
                                    row.latest_source_update_at
                                ),
                                clean_float(
                                    row.quality_score
                                ),
                                clean_float(
                                    row.identity_confidence_score
                                ),
                                clean_bool(row.is_new_1d),
                                clean_bool(row.is_new_7d),
                                clean_bool(row.is_new_30d),
                            )
                        )

                print(
                    "Creating Toronto local entities..."
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
                        phone,
                        industry,
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
                        legal_name,
                        operating_name,
                        local_entity_key,
                        'Toronto, ON',
                        'Active',
                        street,
                        city,
                        province,
                        country,
                        postal_code,
                        phone,
                        industry,
                        COALESCE(
                            first_issued_at,
                            %s
                        ),
                        COALESCE(
                            latest_source_update_at,
                            %s
                        ),
                        COALESCE(
                            latest_source_update_at,
                            %s
                        ),
                        quality_score,
                        confidence_score,
                        is_new_1d,
                        is_new_7d,
                        is_new_30d
                    FROM toronto_entity_stage
                    """,
                    (
                        collected_at,
                        collected_at,
                        collected_at,
                    ),
                )

                local_inserted = cur.rowcount

                if local_inserted != len(entities):
                    raise RuntimeError(
                        "Toronto local entity count mismatch."
                    )

                # ---------------------------------
                # Local source-record staging
                # ---------------------------------

                cur.execute(
                    """
                    CREATE TEMP TABLE toronto_local_source_stage (
                        local_entity_key TEXT,
                        source_record_id TEXT,
                        source_business_name TEXT,
                        phone TEXT,
                        industry TEXT,
                        issued_at TIMESTAMPTZ,
                        source_updated_at TIMESTAMPTZ
                    ) ON COMMIT DROP
                    """
                )

                print(
                    "Copying Toronto local provenance..."
                )

                with cur.copy(
                    """
                    COPY toronto_local_source_stage (
                        local_entity_key,
                        source_record_id,
                        source_business_name,
                        phone,
                        industry,
                        issued_at,
                        source_updated_at
                    )
                    FROM STDIN
                    """
                ) as copy:

                    for row in members.itertuples(
                        index=False
                    ):
                        copy.write_row(
                            (
                                clean(row.local_entity_key),
                                clean(row.source_record_id),
                                clean(row.display_name),
                                clean(row.phone),
                                clean(row.industry),
                                parse_timestamp(
                                    row.issued_at
                                ),
                                parse_timestamp(
                                    row.source_updated_at
                                ),
                            )
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
                        s.source_record_id,
                        s.source_business_name,
                        'Active',
                        s.source_updated_at,
                        %s,
                        s.source_updated_at,
                        jsonb_build_object(
                            'phone', s.phone,
                            'industry', s.industry,
                            'issued_at', s.issued_at
                        )
                    FROM toronto_local_source_stage s
                    JOIN business_entities b
                      ON b.registry_jurisdiction =
                         'Toronto, ON'
                     AND b.province_registry_id =
                         s.local_entity_key
                    """,
                    (
                        source_id,
                        collected_at,
                    ),
                )

                local_source_inserted = cur.rowcount

                # ---------------------------------
                # Strong Federal matches
                # ---------------------------------

                cur.execute(
                    """
                    CREATE TEMP TABLE toronto_federal_stage (
                        source_record_id TEXT,
                        federal_number TEXT,
                        source_business_name TEXT,
                        phone TEXT,
                        industry TEXT,
                        issued_at TIMESTAMPTZ,
                        source_updated_at TIMESTAMPTZ
                    ) ON COMMIT DROP
                    """
                )

                print(
                    "Copying strong Federal matches..."
                )

                with cur.copy(
                    """
                    COPY toronto_federal_stage (
                        source_record_id,
                        federal_number,
                        source_business_name,
                        phone,
                        industry,
                        issued_at,
                        source_updated_at
                    )
                    FROM STDIN
                    """
                ) as copy:

                    for row in strong.itertuples(
                        index=False
                    ):
                        copy.write_row(
                            (
                                clean(row.source_record_id),
                                clean(
                                    row.matched_federal_number
                                ),
                                clean(row.display_name),
                                clean(row.phone),
                                clean(row.industry),
                                parse_timestamp(
                                    row.issued_at
                                ),
                                parse_timestamp(
                                    row.source_updated_at
                                ),
                            )
                        )

                # Preserve Toronto provenance on the
                # existing Federal master entity.
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
                        s.source_record_id,
                        s.source_business_name,
                        'Active',
                        s.source_updated_at,
                        %s,
                        s.source_updated_at,
                        jsonb_build_object(
                            'phone', s.phone,
                            'industry', s.industry,
                            'issued_at', s.issued_at,
                            'match_type',
                            'strong_federal_match'
                        )
                    FROM toronto_federal_stage s
                    JOIN business_entities b
                      ON b.registry_jurisdiction =
                         'Federal'
                     AND b.federal_corporation_number =
                         s.federal_number
                    """,
                    (
                        source_id,
                        collected_at,
                    ),
                )

                federal_source_inserted = cur.rowcount

                if (
                    local_source_inserted
                    + federal_source_inserted
                    != len(matches)
                ):
                    raise RuntimeError(
                        "Toronto provenance count mismatch. "
                        f"Expected {len(matches):,}; got "
                        f"{local_source_inserted + federal_source_inserted:,}."
                    )

                # ---------------------------------
                # Safe Federal enrichment
                # ---------------------------------

                # Only fill fields that are currently
                # missing. Never overwrite Federal data.
                cur.execute(
                    """
                    UPDATE business_entities b
                    SET
                        phone = COALESCE(
                            b.phone,
                            s.phone
                        ),
                        industry = COALESCE(
                            b.industry,
                            s.industry
                        ),
                        last_seen_at = GREATEST(
                            b.last_seen_at,
                            COALESCE(
                                s.source_updated_at,
                                b.last_seen_at
                            )
                        ),
                        last_verified_at = GREATEST(
                            COALESCE(
                                b.last_verified_at,
                                '-infinity'::timestamptz
                            ),
                            COALESCE(
                                s.source_updated_at,
                                '-infinity'::timestamptz
                            )
                        ),
                        updated_at = NOW()
                    FROM toronto_federal_stage s
                    WHERE
                        b.registry_jurisdiction =
                            'Federal'
                        AND
                        b.federal_corporation_number =
                            s.federal_number
                    """
                )

                federal_enriched = cur.rowcount

                # ---------------------------------
                # Source freshness
                # ---------------------------------

                cur.execute(
                    """
                    UPDATE data_sources
                    SET
                        last_source_update_at = (
                            SELECT MAX(
                                source_updated_at
                            )
                            FROM (
                                SELECT
                                    source_updated_at
                                FROM toronto_local_source_stage

                                UNION ALL

                                SELECT
                                    source_updated_at
                                FROM toronto_federal_stage
                            ) x
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

                # ---------------------------------
                # Pipeline metrics
                # ---------------------------------

                cur.execute(
                    """
                    UPDATE pipeline_runs
                    SET
                        finished_at = NOW(),
                        status = 'completed',
                        records_inserted = %s,
                        records_updated = %s,
                        records_deduplicated = %s,
                        records_failed = 0
                    WHERE id = %s
                    """,
                    (
                        local_inserted,
                        federal_enriched,
                        len(matches)
                        - local_inserted,
                        pipeline_run_id,
                    ),
                )

        print(
            "\n=== TORONTO DATABASE LOAD ==="
        )
        print(
            f"Local entities inserted: "
            f"{local_inserted:,}"
        )
        print(
            f"Local provenance records: "
            f"{local_source_inserted:,}"
        )
        print(
            f"Federal provenance records: "
            f"{federal_source_inserted:,}"
        )
        print(
            f"Federal entities enriched: "
            f"{federal_enriched:,}"
        )
        print(
            f"Total Toronto provenance: "
            f"{local_source_inserted + federal_source_inserted:,}"
        )
        print(
            f"Pipeline run ID: {pipeline_run_id}"
        )
        print(
            "\nToronto V2 load completed successfully."
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()