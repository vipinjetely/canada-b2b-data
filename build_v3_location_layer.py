import duckdb
from pathlib import Path

INPUT = "data/processed/v3/businesses_employee_ready.parquet"
OUTPUT = "data/processed/v3/business_locations.parquet"

Path("data/processed/v3").mkdir(parents=True, exist_ok=True)

con = duckdb.connect()

con.execute(f"""
COPY (
    SELECT
        id AS location_id,

        business_name,

        regexp_replace(
            lower(trim(business_name)),
            '[^a-z0-9]',
            '',
            'g'
        ) AS normalized_name,

        basic_category,
        address,
        city,
        province,
        postal_code,
        country,

        phone,
        email,
        website,

        confidence,
        operating_status,
        operating_status_class,

        employee_count,
        employee_size_bucket,
        employee_count_type,
        employee_evidence_source,
        employee_evidence_url,
        employee_verified_at,

        enrichment_priority,

        COUNT(*) OVER (
            PARTITION BY regexp_replace(
                lower(trim(business_name)),
                '[^a-z0-9]',
                '',
                'g'
            )
        ) AS same_name_location_count

    FROM read_parquet('{INPUT}')

    WHERE business_name IS NOT NULL
      AND trim(business_name) <> ''
)
TO '{OUTPUT}'
(FORMAT PARQUET, COMPRESSION ZSTD)
""")

summary = con.execute(f"""
SELECT
    COUNT(*) AS locations,
    COUNT(DISTINCT normalized_name) AS names,

    COUNT(*) FILTER (
        WHERE same_name_location_count = 1
    ) AS single_location_names,

    COUNT(*) FILTER (
        WHERE same_name_location_count > 1
    ) AS repeated_name_locations,

    COUNT(*) FILTER (
        WHERE same_name_location_count >= 10
    ) AS large_chain_locations,

    COUNT(*) FILTER (
        WHERE same_name_location_count >= 100
    ) AS major_chain_locations

FROM read_parquet('{OUTPUT}')
""").fetchone()

print("\\n=== V3 OPERATING LOCATION LAYER ===\\n")

print(f"Total locations          : {summary[0]:,}")
print(f"Unique normalized names  : {summary[1]:,}")
print(f"Single-name locations    : {summary[2]:,}")
print(f"Repeated-name locations  : {summary[3]:,}")
print(f"Locations in 10+ groups  : {summary[4]:,}")
print(f"Locations in 100+ groups : {summary[5]:,}")

print(f"\\nSaved: {OUTPUT}")
print("\\nDONE")