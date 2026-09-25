import os

import psycopg
from dotenv import load_dotenv


load_dotenv()


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "canada_b2b"),
        user=os.getenv("POSTGRES_USER", "canada_b2b_user"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def fetch_value(query):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchone()[0]


def test_v2_has_canonical_entities():
    count = fetch_value(
        "SELECT COUNT(*) FROM business_entities;"
    )
    assert count > 0


def test_v2_has_source_provenance():
    count = fetch_value(
        "SELECT COUNT(*) FROM business_source_records;"
    )
    assert count > 0


def test_v2_has_six_active_sources():
    count = fetch_value(
        """
        SELECT COUNT(*)
        FROM data_sources
        WHERE is_active = TRUE;
        """
    )
    assert count >= 6


def test_v2_has_no_orphan_provenance():
    count = fetch_value(
        """
        SELECT COUNT(*)
        FROM business_source_records bsr
        LEFT JOIN business_entities be
            ON be.id = bsr.business_id
        WHERE be.id IS NULL;
        """
    )
    assert count == 0


def test_v2_has_no_duplicate_federal_ids():
    count = fetch_value(
        """
        SELECT COUNT(*)
        FROM (
            SELECT federal_corporation_number
            FROM business_entities
            WHERE federal_corporation_number IS NOT NULL
            GROUP BY federal_corporation_number
            HAVING COUNT(*) > 1
        ) duplicates;
        """
    )
    assert count == 0


def test_v2_has_no_duplicate_provincial_ids():
    count = fetch_value(
        """
        SELECT COUNT(*)
        FROM (
            SELECT
                registry_jurisdiction,
                province_registry_id
            FROM business_entities
            WHERE province_registry_id IS NOT NULL
            GROUP BY
                registry_jurisdiction,
                province_registry_id
            HAVING COUNT(*) > 1
        ) duplicates;
        """
    )
    assert count == 0


def test_v2_all_expected_sources_exist():
    expected = {
        "corporations_canada",
        "vancouver_business_licences",
        "toronto_business_licences",
        "edmonton_business_licences",
        "calgary_business_licences",
        "quebec_rbq_active_licences",
    }

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_key
                FROM data_sources
                WHERE is_active = TRUE;
                """
            )
            actual = {row[0] for row in cur.fetchall()}

    assert expected.issubset(actual)


def test_v2_recorded_source_loads_have_no_failures():
    count = fetch_value(
        """
        SELECT COUNT(*)
        FROM pipeline_runs
        WHERE records_failed > 0;
        """
    )
    assert count == 0


def test_v2_entities_have_source_links():
    count = fetch_value(
        """
        SELECT COUNT(*)
        FROM business_entities be
        WHERE NOT EXISTS (
            SELECT 1
            FROM business_source_records bsr
            WHERE bsr.business_id = be.id
        );
        """
    )
    assert count == 0