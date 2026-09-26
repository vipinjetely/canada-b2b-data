import os
import re
from pathlib import Path

import duckdb
import pandas as pd
import psycopg
from dotenv import load_dotenv

load_dotenv()

INPUT = "data/processed/v3/entity_resolution_base.parquet"
OUTPUT = "data/processed/v3/vancouver_employee_enrichment.parquet"

Path("data/processed/v3").mkdir(parents=True, exist_ok=True)

conn = psycopg.connect(
    host=os.getenv("POSTGRES_HOST", "localhost"),
    port=os.getenv("POSTGRES_PORT", "5432"),
    dbname=os.getenv("POSTGRES_DB", "canada_b2b"),
    user=os.getenv("POSTGRES_USER", "canada_b2b_user"),
    password=os.getenv("POSTGRES_PASSWORD"),
)

with conn.cursor() as cur:
    cur.execute("""
        SELECT
            id,
            COALESCE(operating_name, legal_name) AS business_name,
            postal_code,
            employee_count,
            employee_size_bucket,
            last_verified_at
        FROM business_entities
        WHERE registry_jurisdiction = 'Vancouver, BC'
          AND employee_count IS NOT NULL
    """)

    rows = cur.fetchall()

conn.close()

gov = pd.DataFrame(
    rows,
    columns=[
        "v2_id",
        "business_name",
        "postal_code",
        "employee_count",
        "employee_size_bucket",
        "last_verified_at",
    ],
)


def norm_name(value):
    if value is None:
        return ""

    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def norm_postal(value):
    if value is None:
        return ""

    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


gov["norm_name"] = gov["business_name"].map(norm_name)
gov["norm_postal"] = gov["postal_code"].map(norm_postal)

con = duckdb.connect()
con.register("gov", gov)

con.execute(f"""
CREATE OR REPLACE TEMP TABLE candidates AS

SELECT
    o.location_id,
    o.business_name AS overture_business_name,
    o.city,
    o.province,
    o.postal_code,

    g.v2_id,
    g.business_name AS government_business_name,
    g.employee_count,
    g.employee_size_bucket,
    g.last_verified_at,

    'NAME_POSTAL' AS match_method

FROM read_parquet('{INPUT}') o

JOIN gov g
  ON o.normalized_name = g.norm_name
 AND o.normalized_postal = g.norm_postal

WHERE upper(coalesce(o.province, '')) IN (
    'BC',
    'BRITISH COLUMBIA'
)
AND o.normalized_name <> ''
AND o.normalized_postal <> ''
""")

con.execute("""
CREATE OR REPLACE TEMP TABLE safe_matches AS

SELECT *
FROM candidates
WHERE location_id IN (
    SELECT location_id
    FROM candidates
    GROUP BY location_id
    HAVING COUNT(DISTINCT v2_id) = 1
)
AND v2_id IN (
    SELECT v2_id
    FROM candidates
    GROUP BY v2_id
    HAVING COUNT(DISTINCT location_id) = 1
)
""")

con.execute(f"""
COPY (
    SELECT
        location_id,
        v2_id AS government_entity_id,
        overture_business_name,
        government_business_name,
        city,
        province,
        postal_code,
        employee_count,
        employee_size_bucket,
        'VERIFIED' AS employee_count_type,
        'Vancouver Business Licences' AS employee_evidence_source,
        last_verified_at AS employee_verified_at,
        match_method,
        'LOCATION' AS employee_evidence_scope
    FROM safe_matches
)
TO '{OUTPUT}'
(FORMAT PARQUET, COMPRESSION ZSTD)
""")

candidate_count = con.execute("""
    SELECT COUNT(DISTINCT location_id)
    FROM candidates
""").fetchone()[0]

safe_count = con.execute("""
    SELECT COUNT(*)
    FROM safe_matches
""").fetchone()[0]

unique_gov = con.execute("""
    SELECT COUNT(DISTINCT v2_id)
    FROM safe_matches
""").fetchone()[0]

print("\n=== VANCOUVER VERIFIED EMPLOYEE ENRICHMENT ===\n")
print(f"Candidate locations     : {candidate_count:,}")
print(f"Safe one-to-one matches : {safe_count:,}")
print(f"Government records used : {unique_gov:,}")

print(f"\nSaved: {OUTPUT}")
print("\nNO DATABASE RECORDS MODIFIED")
print("DONE")