import duckdb
from pathlib import Path

BASE = "data/processed/v3/entity_resolution_base.parquet"
EMPLOYEE = "data/processed/v3/vancouver_employee_enrichment.parquet"
OUTPUT = "data/processed/v3/business_locations_enriched.parquet"

Path("data/processed/v3").mkdir(parents=True, exist_ok=True)

con = duckdb.connect()

print("\nApplying verified Vancouver employee enrichment...")

con.execute(f"""
COPY (
    SELECT
        b.* EXCLUDE (
            employee_count,
            employee_size_bucket,
            employee_count_type,
            employee_evidence_source,
            employee_evidence_url,
            employee_verified_at
        ),

        COALESCE(
            e.employee_count,
            b.employee_count
        ) AS employee_count,

        COALESCE(
            e.employee_size_bucket,
            b.employee_size_bucket
        ) AS employee_size_bucket,

        CASE
            WHEN e.location_id IS NOT NULL
                THEN 'VERIFIED'
            ELSE COALESCE(
                b.employee_count_type,
                'UNKNOWN'
            )
        END AS employee_count_type,

        CASE
            WHEN e.location_id IS NOT NULL
                THEN e.employee_evidence_source
            ELSE b.employee_evidence_source
        END AS employee_evidence_source,

        CASE
            WHEN e.location_id IS NOT NULL
                THEN NULL
            ELSE b.employee_evidence_url
        END AS employee_evidence_url,

        CASE
            WHEN e.location_id IS NOT NULL
                THEN e.employee_verified_at
            ELSE b.employee_verified_at
        END AS employee_verified_at,

        CASE
            WHEN e.location_id IS NOT NULL
                THEN e.government_entity_id
            ELSE NULL
        END AS employee_government_entity_id,

        CASE
            WHEN e.location_id IS NOT NULL
                THEN e.match_method
            ELSE NULL
        END AS employee_match_method,

        CASE
            WHEN e.location_id IS NOT NULL
                THEN e.employee_evidence_scope
            ELSE NULL
        END AS employee_evidence_scope

    FROM read_parquet('{BASE}') b

    LEFT JOIN read_parquet('{EMPLOYEE}') e
      ON b.location_id = e.location_id
)
TO '{OUTPUT}'
(FORMAT PARQUET, COMPRESSION ZSTD)
""")

summary = con.execute(f"""
SELECT
    COUNT(*) AS total,

    COUNT(*) FILTER (
        WHERE employee_count_type = 'VERIFIED'
    ) AS verified,

    COUNT(*) FILTER (
        WHERE employee_count_type = 'UNKNOWN'
    ) AS unknown,

    COUNT(*) FILTER (
        WHERE employee_count IS NOT NULL
    ) AS with_count,

    COUNT(*) FILTER (
        WHERE employee_size_bucket IS NOT NULL
    ) AS with_bucket,

    COUNT(*) FILTER (
        WHERE employee_evidence_scope = 'LOCATION'
    ) AS location_scope

FROM read_parquet('{OUTPUT}')
""").fetchone()

duplicates = con.execute(f"""
SELECT COUNT(*)
FROM (
    SELECT location_id
    FROM read_parquet('{OUTPUT}')
    GROUP BY location_id
    HAVING COUNT(*) > 1
)
""").fetchone()[0]

print("\n=== V3 EMPLOYEE ENRICHMENT RESULT ===\n")

print(f"Total locations        : {summary[0]:,}")
print(f"Verified employee data : {summary[1]:,}")
print(f"Unknown employee data  : {summary[2]:,}")
print(f"With employee count    : {summary[3]:,}")
print(f"With employee bucket   : {summary[4]:,}")
print(f"Location-scope evidence: {summary[5]:,}")
print(f"Duplicate location IDs : {duplicates:,}")

print(f"\nSaved: {OUTPUT}")
print("\nSOURCE FILES NOT MODIFIED")
print("DONE")