from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv


ENTITIES_FILE = Path(
    "data/processed/v2/entity_resolution/calgary_local_entities.csv"
)
MEMBERS_FILE = Path(
    "data/processed/v2/entity_resolution/calgary_entity_members.csv"
)
MATCHES_FILE = Path(
    "data/processed/v2/entity_resolution/calgary_federal_matches.csv"
)
METADATA_FILE = Path(
    "data/raw/v2/calgary_business_licences_metadata.json"
)

SOURCE_KEY = "calgary_business_licences"
JURISDICTION = "Calgary, AB"


def clean(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if value.lower() in {"", "nan", "none", "<na>", "null"}:
        return None

    return value


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
    }


def main() -> None:
    load_dotenv()

    print("Reading Calgary entity-resolution outputs...")

    entities = pd.read_csv(
        ENTITIES_FILE,
        dtype=str,
        keep_default_na=False,
    )

    members = pd.read_csv(
        MEMBERS_FILE,
        dtype=str,
        keep_default_na=False,
    )

    matches = pd.read_csv(
        MATCHES_FILE,
        dtype=str,
        keep_default_na=False,
    )

    with METADATA_FILE.open("r", encoding="utf-8") as f:
        metadata = json.load(f)

    strong = matches[
        matches["federal_match_category"]
        == "FEDERAL_NAME_CITY_ADDRESS"
    ].copy()

    print(f"Local canonical entities: {len(entities):,}")
    print(f"Local source records: {len(members):,}")
    print(f"Strong federal matches: {len(strong):,}")

    if len(members) + len(strong) != len(matches):
        raise RuntimeError(
            "Calgary reconciliation failed."
        )

    if len(strong):
        raise RuntimeError(
            "Strong Calgary Federal matches exist. "
            "This loader expects zero strong matches."
        )

    conninfo = (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'canada_b2b')} "
        f"user={os.getenv('POSTGRES_USER', 'canada_b2b_user')} "
        f"password={os.getenv('POSTGRES_PASSWORD', '')}"
    )

    with psycopg.connect(conninfo) as conn:
        with conn.transaction():
            with conn.cursor() as cur:

                # -------------------------------------------------
                # Source
                # -------------------------------------------------

                cur.execute(
                    """
                    SELECT id
                    FROM data_sources
                    WHERE source_key = %s
                      AND is_active = TRUE
                    """,
                    (SOURCE_KEY,),
                )

                source_row = cur.fetchone()

                if not source_row:
                    raise RuntimeError(
                        "Calgary source is not registered."
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
                        f"Calgary already has "
                        f"{existing:,} provenance records."
                    )

                # -------------------------------------------------
                # Pipeline run
                # -------------------------------------------------

                cur.execute(
                    """
                    INSERT INTO pipeline_runs (
                        started_at,
                        status,
                        records_collected,
                        records_inserted,
                        records_updated,
                        records_deduplicated,
                        records_failed
                    )
                    VALUES (
                        NOW(),
                        'RUNNING',
                        %s,
                        0,
                        0,
                        0,
                        0
                    )
                    RETURNING id
                    """,
                    (len(matches),),
                )

                pipeline_run_id = cur.fetchone()[0]

                # -------------------------------------------------
                # Canonical entity staging
                # -------------------------------------------------

                cur.execute(
                    """
                    CREATE TEMP TABLE calgary_entity_stage (
                        canonical_key TEXT NOT NULL,
                        legal_name TEXT NOT NULL,
                        operating_name TEXT,
                        street TEXT,
                        city TEXT,
                        province TEXT,
                        country TEXT,
                        postal_code TEXT,
                        industry TEXT,
                        status TEXT,
                        identity_quality TEXT,
                        identity_confidence INTEGER,
                        collected_at_utc TIMESTAMPTZ,
                        is_new_1d BOOLEAN,
                        is_new_7d BOOLEAN,
                        is_new_30d BOOLEAN
                    ) ON COMMIT DROP
                    """
                )

                print("Copying Calgary canonical entities...")

                with cur.copy(
                    """
                    COPY calgary_entity_stage (
                        canonical_key,
                        legal_name,
                        operating_name,
                        street,
                        city,
                        province,
                        country,
                        postal_code,
                        industry,
                        status,
                        identity_quality,
                        identity_confidence,
                        collected_at_utc,
                        is_new_1d,
                        is_new_7d,
                        is_new_30d
                    )
                    FROM STDIN
                    """
                ) as copy:

                    for row in entities.itertuples(index=False):

                        legal_name = clean(row.legal_name)

                        if not legal_name:
                            raise RuntimeError(
                                "Calgary entity has invalid legal name: "
                                f"{row.canonical_key}"
                            )

                        copy.write_row(
                            (
                                clean(row.canonical_key),
                                legal_name,
                                clean(row.operating_name),
                                clean(row.street),
                                clean(row.city),
                                clean(row.province),
                                clean(row.country),
                                clean(row.postal_code),
                                clean(row.industry),
                                clean(row.status),
                                clean(row.identity_quality),
                                int(row.identity_confidence),
                                clean(row.collected_at_utc),
                                as_bool(row.is_new_1d),
                                as_bool(row.is_new_7d),
                                as_bool(row.is_new_30d),
                            )
                        )

                # -------------------------------------------------
                # Insert canonical entities
                # -------------------------------------------------

                print("Creating Calgary local entities...")

                cur.execute(
                    """
                    INSERT INTO business_entities (
                        legal_name,
                        operating_name,
                        registry_jurisdiction,
                        status,
                        street,
                        city,
                        province,
                        country,
                        postal_code,
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
                        %s,
                        status,
                        street,
                        city,
                        province,
                        country,
                        postal_code,
                        industry,
                        collected_at_utc,
                        collected_at_utc,
                        collected_at_utc,
                        CASE
                            WHEN identity_quality = 'HIGH_CONFIDENCE'
                            THEN 95
                            ELSE 70
                        END,
                        identity_confidence,
                        is_new_1d,
                        is_new_7d,
                        is_new_30d
                    FROM calgary_entity_stage
                    """,
                    (JURISDICTION,),
                )

                inserted_entities = cur.rowcount

                if inserted_entities != len(entities):
                    raise RuntimeError(
                        "Calgary entity insert mismatch: "
                        f"{inserted_entities:,} inserted vs "
                        f"{len(entities):,} expected."
                    )

                # -------------------------------------------------
                # Build entity ID map
                # -------------------------------------------------

                cur.execute(
                    """
                    CREATE TEMP TABLE calgary_entity_map AS
                    SELECT
                        s.canonical_key,
                        b.id AS business_id
                    FROM calgary_entity_stage s
                    JOIN business_entities b
                      ON b.registry_jurisdiction = %s
                     AND b.legal_name = s.legal_name
                     AND COALESCE(b.street, '') =
                         COALESCE(s.street, '')
                     AND COALESCE(b.city, '') =
                         COALESCE(s.city, '')
                    """,
                    (JURISDICTION,),
                )

                cur.execute(
                    """
                    SELECT
                        COUNT(*),
                        COUNT(DISTINCT canonical_key),
                        COUNT(DISTINCT business_id)
                    FROM calgary_entity_map
                    """
                )

                (
                    map_rows,
                    map_keys,
                    map_business_ids,
                ) = cur.fetchone()

                if (
                    map_rows != len(entities)
                    or map_keys != len(entities)
                    or map_business_ids != len(entities)
                ):
                    raise RuntimeError(
                        "Calgary entity mapping is not 1:1. "
                        f"rows={map_rows:,}, "
                        f"keys={map_keys:,}, "
                        f"business_ids={map_business_ids:,}, "
                        f"expected={len(entities):,}"
                    )

                # -------------------------------------------------
                # Provenance staging
                # -------------------------------------------------

                cur.execute(
                    """
                    CREATE TEMP TABLE calgary_member_stage (
                        source_record_id TEXT NOT NULL,
                        canonical_key TEXT NOT NULL,
                        legal_name TEXT,
                        status TEXT,
                        first_issue_date TIMESTAMPTZ,
                        expiry_date TIMESTAMPTZ,
                        collected_at_utc TIMESTAMPTZ
                    ) ON COMMIT DROP
                    """
                )

                print("Copying Calgary local provenance...")

                with cur.copy(
                    """
                    COPY calgary_member_stage (
                        source_record_id,
                        canonical_key,
                        legal_name,
                        status,
                        first_issue_date,
                        expiry_date,
                        collected_at_utc
                    )
                    FROM STDIN
                    """
                ) as copy:

                    for row in members.itertuples(index=False):
                        copy.write_row(
                            (
                                clean(row.source_record_id),
                                clean(row.canonical_key),
                                clean(row.legal_name),
                                clean(row.status),
                                clean(row.first_issue_date),
                                clean(row.expiry_date),
                                clean(row.collected_at_utc),
                            )
                        )

                # -------------------------------------------------
                # Provenance
                # -------------------------------------------------

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
                        m.business_id,
                        %s,
                        s.source_record_id,
                        s.legal_name,
                        s.status,
                        COALESCE(
                            s.expiry_date,
                            s.first_issue_date,
                            s.collected_at_utc
                        ),
                        s.collected_at_utc,
                        s.collected_at_utc,
                        jsonb_build_object(
                            'source_record_id',
                            s.source_record_id,
                            'canonical_key',
                            s.canonical_key,
                            'first_issue_date',
                            s.first_issue_date,
                            'expiry_date',
                            s.expiry_date
                        )
                    FROM calgary_member_stage s
                    JOIN calgary_entity_map m
                      ON m.canonical_key = s.canonical_key
                    """,
                    (source_id,),
                )

                inserted_provenance = cur.rowcount

                if inserted_provenance != len(members):
                    raise RuntimeError(
                        "Calgary provenance mismatch: "
                        f"{inserted_provenance:,} inserted vs "
                        f"{len(members):,} expected."
                    )

                # -------------------------------------------------
                # Source freshness
                # -------------------------------------------------

                cur.execute(
                    """
                    UPDATE data_sources
                    SET
                        last_collected_at = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        metadata["collected_at_utc"],
                        source_id,
                    ),
                )

                # -------------------------------------------------
                # Pipeline success
                # -------------------------------------------------

                deduplicated = len(matches) - inserted_entities

                cur.execute(
                    """
                    UPDATE pipeline_runs
                    SET
                        status = 'SUCCESS',
                        finished_at = NOW(),
                        records_collected = %s,
                        records_inserted = %s,
                        records_updated = 0,
                        records_deduplicated = %s,
                        records_failed = 0,
                        error_message = NULL
                    WHERE id = %s
                    """,
                    (
                        len(matches),
                        inserted_entities,
                        deduplicated,
                        pipeline_run_id,
                    ),
                )

                print()
                print("=== CALGARY DATABASE LOAD ===")
                print(
                    f"Local entities inserted: "
                    f"{inserted_entities:,}"
                )
                print(
                    f"Local provenance records: "
                    f"{inserted_provenance:,}"
                )
                print("Federal provenance records: 0")
                print(
                    f"Total Calgary provenance: "
                    f"{inserted_provenance:,}"
                )
                print(
                    f"Licence records collapsed into "
                    f"canonical entities: {deduplicated:,}"
                )
                print(f"Pipeline run ID: {pipeline_run_id}")

    print()
    print("Calgary V2 load completed successfully.")


if __name__ == "__main__":
    main()