from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT / "data" / "processed" / "v3"

BUSINESS = V3 / "overture_business_candidates_v2.parquet"
LOCATIONS = V3 / "business_locations.parquet"
RESOLUTION = V3 / "entity_resolution_base.parquet"
ENRICHED = V3 / "business_locations_enriched.parquet"
VANCOUVER = V3 / "vancouver_employee_enrichment.parquet"


def scalar(sql):
    con = duckdb.connect()
    try:
        return con.execute(sql).fetchone()[0]
    finally:
        con.close()


def pq(path):
    return path.as_posix()


def test_required_v3_files_exist():
    for path in [
        BUSINESS,
        LOCATIONS,
        RESOLUTION,
        ENRICHED,
        VANCOUVER,
    ]:
        assert path.exists(), f"Missing: {path}"


def test_business_candidate_count():
    count = scalar(
        f"SELECT COUNT(*) FROM read_parquet('{pq(BUSINESS)}')"
    )
    assert count == 1_183_392


def test_location_count_preserved():
    source = scalar(
        f"SELECT COUNT(*) FROM read_parquet('{pq(BUSINESS)}')"
    )
    locations = scalar(
        f"SELECT COUNT(*) FROM read_parquet('{pq(LOCATIONS)}')"
    )
    assert locations == source


def test_resolution_count_preserved():
    locations = scalar(
        f"SELECT COUNT(*) FROM read_parquet('{pq(LOCATIONS)}')"
    )
    resolved = scalar(
        f"SELECT COUNT(*) FROM read_parquet('{pq(RESOLUTION)}')"
    )
    assert resolved == locations


def test_enrichment_count_preserved():
    resolved = scalar(
        f"SELECT COUNT(*) FROM read_parquet('{pq(RESOLUTION)}')"
    )
    enriched = scalar(
        f"SELECT COUNT(*) FROM read_parquet('{pq(ENRICHED)}')"
    )
    assert enriched == resolved


def test_location_ids_unique():
    duplicates = scalar(
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT location_id
            FROM read_parquet('{pq(ENRICHED)}')
            GROUP BY location_id
            HAVING COUNT(*) > 1
        )
        """
    )
    assert duplicates == 0


def test_verified_employee_count():
    count = scalar(
        f"""
        SELECT COUNT(*)
        FROM read_parquet('{pq(ENRICHED)}')
        WHERE employee_count_type = 'VERIFIED'
        """
    )
    assert count == 3_653


def test_verified_employee_evidence_complete():
    invalid = scalar(
        f"""
        SELECT COUNT(*)
        FROM read_parquet('{pq(ENRICHED)}')
        WHERE employee_count_type = 'VERIFIED'
          AND (
              employee_count IS NULL
              OR employee_size_bucket IS NULL
              OR employee_evidence_source IS NULL
              OR employee_verified_at IS NULL
              OR employee_evidence_scope <> 'LOCATION'
          )
        """
    )
    assert invalid == 0


def test_unknown_employee_counts_not_fabricated():
    invalid = scalar(
        f"""
        SELECT COUNT(*)
        FROM read_parquet('{pq(ENRICHED)}')
        WHERE employee_count_type = 'UNKNOWN'
          AND (
              employee_count IS NOT NULL
              OR employee_size_bucket IS NOT NULL
          )
        """
    )
    assert invalid == 0


def test_vancouver_safe_match_count():
    count = scalar(
        f"SELECT COUNT(*) FROM read_parquet('{pq(VANCOUVER)}')"
    )
    assert count == 3_653