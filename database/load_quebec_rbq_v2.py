from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv


PROCESSED_DIR = Path("data/processed/v2")
RAW_DIR = Path("data/raw/v2")
ER_DIR = PROCESSED_DIR / "entity_resolution"

LOCAL_ENTITIES_FILE = (
    ER_DIR / "quebec_rbq_local_entities.csv"
)

LOCAL_SOURCE_RECORDS_FILE = (
    ER_DIR / "quebec_rbq_local_source_records.csv"
)

FEDERAL_MATCHES_FILE = (
    ER_DIR / "quebec_rbq_federal_matches.csv"
)

METADATA_FILE = (
    RAW_DIR / "quebec_rbq_active_licences_metadata.json"
)

SOURCE_KEY = "quebec_rbq_active_licences"


def value_or_none(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def number_or_none(value):
    value = value_or_none(value)

    if value is None:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def connect():
    load_dotenv()

    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def main():
    print(
        "Reading Québec RBQ entity-resolution outputs..."
    )

    local_entities = pd.read_csv(
        LOCAL_ENTITIES_FILE,
        dtype=str,
        low_memory=False,
    )

    local_records = pd.read_csv(
        LOCAL_SOURCE_RECORDS_FILE,
        dtype=str,
        low_memory=False,
    )

    federal_matches = pd.read_csv(
        FEDERAL_MATCHES_FILE,
        dtype=str,
        low_memory=False,
    )

    metadata = json.loads(
        METADATA_FILE.read_text(
            encoding="utf-8"
        )
    )

    print(
        f"Local canonical entities: {len(local_entities):,}"
    )

    print(
        f"Local source records: {len(local_records):,}"
    )

    print(
        f"Strong Federal matches: {len(federal_matches):,}"
    )

    conn = connect()

    try:
        with conn.transaction():

            with conn.cursor() as cur:

                # ------------------------------------
                # Source
                # ------------------------------------

                cur.execute(
                    """
                    SELECT id
                    FROM data_sources
                    WHERE source_key = %s
                    """,
                    (SOURCE_KEY,),
                )

                source_row = cur.fetchone()

                if source_row is None:
                    cur.execute(
                        """
                        INSERT INTO data_sources (
                            source_key,
                            source_name,
                            source_type,
                            jurisdiction,
                            source_url,
                            update_frequency,
                            licence_name,
                            commercial_use_allowed,
                            last_source_update_at,
                            last_collected_at,
                            is_active
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, TRUE
                        )
                        RETURNING id
                        """,
                        (
                            SOURCE_KEY,
                            (
                                "Régie du bâtiment du Québec "
                                "- Liste des licences actives"
                            ),
                            "provincial_business_licence",
                            "Québec, QC",
                            metadata["source_url"],
                            "daily",
                            "CC BY 4.0",
                            True,
                            metadata.get("last_modified"),
                            metadata["collected_at_utc"],
                        ),
                    )

                    source_id = cur.fetchone()[0]

                else:
                    source_id = source_row[0]

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
                            metadata.get("last_modified"),
                            metadata["collected_at_utc"],
                            source_id,
                        ),
                    )

                # ------------------------------------
                # Pipeline run
                # ------------------------------------

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
                    (
                        len(local_records)
                        + len(federal_matches),
                    ),
                )

                pipeline_run_id = cur.fetchone()[0]

                # ------------------------------------
                # Create local Québec entities
                # ------------------------------------

                print(
                    "Creating Québec local entities..."
                )

                identity_to_business_id = {}

                inserted_entities = 0

                for row in local_entities.itertuples(
                    index=False
                ):

                    identity_key = value_or_none(
                        row.canonical_identity_key
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
                            phone,
                            email,
                            industry,
                            first_seen_at,
                            last_seen_at,
                            last_verified_at,
                            quality_score,
                            confidence_score,
                            do_not_call,
                            is_new_1d,
                            is_new_7d,
                            is_new_30d
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            FALSE,
                            FALSE, FALSE, FALSE
                        )
                        RETURNING id
                        """,
                        (
                            value_or_none(
                                row.legal_name
                            ),
                            value_or_none(
                                row.operating_name
                            ),
                            value_or_none(
                                row.neq
                            ),
                            "Québec, QC",
                            value_or_none(
                                row.licence_status
                            ),
                            value_or_none(
                                row.address
                            ),
                            value_or_none(
                                row.city
                            ),
                            "QC",
                            "CA",
                            value_or_none(
                                row.phone
                            ),
                            value_or_none(
                                row.email
                            ),
                            value_or_none(
                                row.category
                            ),
                            metadata[
                                "collected_at_utc"
                            ],
                            metadata[
                                "collected_at_utc"
                            ],
                            metadata[
                                "collected_at_utc"
                            ],
                            number_or_none(
                                row.quality_score
                            ),
                            number_or_none(
                                row.quality_score
                            ),
                        ),
                    )

                    business_id = cur.fetchone()[0]

                    identity_to_business_id[
                        identity_key
                    ] = business_id

                    inserted_entities += 1

                # ------------------------------------
                # Local provenance
                # ------------------------------------

                print(
                    "Creating Québec local provenance..."
                )

                local_provenance = 0

                for row in local_records.itertuples(
                    index=False
                ):

                    identity_key = value_or_none(
                        row.canonical_identity_key
                    )

                    business_id = (
                        identity_to_business_id.get(
                            identity_key
                        )
                    )

                    if business_id is None:
                        raise RuntimeError(
                            "Missing local business ID "
                            f"for {identity_key}"
                        )

                    raw_record = {
                        column: (
                            None
                            if pd.isna(value)
                            else str(value)
                        )
                        for column, value in (
                            row._asdict().items()
                        )
                    }

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
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s::jsonb
                        )
                        """,
                        (
                            business_id,
                            source_id,
                            value_or_none(
                                row.source_record_id
                            ),
                            value_or_none(
                                row.legal_name
                            ),
                            value_or_none(
                                row.licence_status
                            ),
                            metadata.get(
                                "last_modified"
                            ),
                            metadata[
                                "collected_at_utc"
                            ],
                            metadata[
                                "collected_at_utc"
                            ],
                            json.dumps(
                                raw_record,
                                ensure_ascii=False,
                            ),
                        ),
                    )

                    local_provenance += 1

                # ------------------------------------
                # Strong Federal matches
                # ------------------------------------

                print(
                    "Linking strong Federal matches..."
                )

                federal_provenance = 0
                federal_entities_enriched = set()

                rbq_lookup = (
                    pd.read_csv(
                        PROCESSED_DIR
                        / "quebec_rbq_licences_normalized.csv",
                        dtype=str,
                        low_memory=False,
                    )
                    .set_index("source_record_id")
                )

                for row in federal_matches.itertuples(
                    index=False
                ):

                    federal_number = value_or_none(
                        row.federal_corporation_number
                    )

                    source_record_id = value_or_none(
                        row.source_record_id
                    )

                    cur.execute(
                        """
                        SELECT id
                        FROM business_entities
                        WHERE federal_corporation_number = %s
                        LIMIT 1
                        """,
                        (federal_number,),
                    )

                    result = cur.fetchone()

                    if result is None:
                        raise RuntimeError(
                            "Federal entity not found: "
                            f"{federal_number}"
                        )

                    business_id = result[0]

                    rbq_row = rbq_lookup.loc[
                        source_record_id
                    ]

                    if isinstance(
                        rbq_row,
                        pd.DataFrame,
                    ):
                        rbq_row = rbq_row.iloc[0]

                    raw_record = {
                        column: (
                            None
                            if pd.isna(value)
                            else str(value)
                        )
                        for column, value
                        in rbq_row.items()
                    }

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
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s::jsonb
                        )
                        """,
                        (
                            business_id,
                            source_id,
                            source_record_id,
                            value_or_none(
                                rbq_row.get(
                                    "legal_name"
                                )
                            ),
                            value_or_none(
                                rbq_row.get(
                                    "licence_status"
                                )
                            ),
                            metadata.get(
                                "last_modified"
                            ),
                            metadata[
                                "collected_at_utc"
                            ],
                            metadata[
                                "collected_at_utc"
                            ],
                            json.dumps(
                                raw_record,
                                ensure_ascii=False,
                            ),
                        ),
                    )

                    federal_provenance += 1

                    # Enrich only missing fields.
                    cur.execute(
                        """
                        UPDATE business_entities
                        SET
                            phone = COALESCE(phone, %s),
                            email = COALESCE(email, %s),
                            industry = COALESCE(
                                industry,
                                %s
                            ),
                            last_seen_at = %s,
                            last_verified_at = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            value_or_none(
                                rbq_row.get("phone")
                            ),
                            value_or_none(
                                rbq_row.get("email")
                            ),
                            value_or_none(
                                rbq_row.get("category")
                            ),
                            metadata[
                                "collected_at_utc"
                            ],
                            metadata[
                                "collected_at_utc"
                            ],
                            business_id,
                        ),
                    )

                    federal_entities_enriched.add(
                        business_id
                    )

                # ------------------------------------
                # Finish pipeline run
                # ------------------------------------

                deduplicated = (
                    len(local_records)
                    - inserted_entities
                    + len(federal_matches)
                )

                cur.execute(
                    """
                    UPDATE pipeline_runs
                    SET
                        finished_at = NOW(),
                        status = 'SUCCESS',
                        records_inserted = %s,
                        records_updated = %s,
                        records_deduplicated = %s,
                        records_failed = 0
                    WHERE id = %s
                    """,
                    (
                        inserted_entities,
                        len(
                            federal_entities_enriched
                        ),
                        deduplicated,
                        pipeline_run_id,
                    ),
                )

                print()
                print(
                    "=== QUÉBEC RBQ DATABASE LOAD ==="
                )

                print(
                    "Local entities inserted: "
                    f"{inserted_entities:,}"
                )

                print(
                    "Local provenance records: "
                    f"{local_provenance:,}"
                )

                print(
                    "Federal provenance records: "
                    f"{federal_provenance:,}"
                )

                print(
                    "Federal entities enriched: "
                    f"{len(federal_entities_enriched):,}"
                )

                print(
                    "Total Québec provenance: "
                    f"{local_provenance + federal_provenance:,}"
                )

                print(
                    "Licence records collapsed / "
                    "linked to existing entities: "
                    f"{deduplicated:,}"
                )

                print(
                    f"Pipeline run ID: {pipeline_run_id}"
                )

        print()
        print(
            "Québec RBQ V2 load completed successfully."
        )

    except Exception:
        conn.rollback()

        print()
        print(
            "Québec RBQ load failed. "
            "Transaction rolled back."
        )

        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()