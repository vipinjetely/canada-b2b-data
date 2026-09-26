import duckdb
from pathlib import Path

INPUT = "data/processed/v3/overture_business_candidates_v2.parquet"
OUTPUT = "data/processed/v3/businesses_employee_ready.parquet"

Path("data/processed/v3").mkdir(parents=True, exist_ok=True)

con = duckdb.connect()

con.execute(f"""
COPY (
    SELECT
        *,

        CAST(NULL AS INTEGER) AS employee_count,
        CAST(NULL AS VARCHAR) AS employee_size_bucket,

        'UNKNOWN'::VARCHAR AS employee_count_type,

        CAST(NULL AS VARCHAR) AS employee_evidence_source,
        CAST(NULL AS VARCHAR) AS employee_evidence_url,
        CAST(NULL AS TIMESTAMP) AS employee_verified_at,

        CASE
            WHEN phone IS NOT NULL
             AND website IS NOT NULL
             AND email IS NOT NULL THEN 'HIGH_CONTACT_COVERAGE'

            WHEN phone IS NOT NULL
              OR website IS NOT NULL
              OR email IS NOT NULL THEN 'PARTIAL_CONTACT_COVERAGE'

            ELSE 'LOW_CONTACT_COVERAGE'
        END AS enrichment_priority

    FROM read_parquet('{INPUT}')
)
TO '{OUTPUT}'
(FORMAT PARQUET, COMPRESSION ZSTD)
""")

row = con.execute(f"""
SELECT
    COUNT(*) AS total,
    COUNT(phone) AS phone,
    COUNT(email) AS email,
    COUNT(website) AS website,
    SUM(CASE WHEN enrichment_priority='HIGH_CONTACT_COVERAGE'
             THEN 1 ELSE 0 END) AS high_contact
FROM read_parquet('{OUTPUT}')
""").fetchone()

print("\n=== V3 EMPLOYEE-READY BASE ===\n")
print(f"Businesses       : {row[0]:,}")
print(f"With phone       : {row[1]:,}")
print(f"With email       : {row[2]:,}")
print(f"With website     : {row[3]:,}")
print(f"High contact     : {row[4]:,}")
print("\nEmployee status  : UNKNOWN until supported by evidence")
print(f"\nSaved: {OUTPUT}")
print("DONE")