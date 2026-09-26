import duckdb
from pathlib import Path

INPUT = "data/processed/v3/business_locations.parquet"
OUTPUT = "data/processed/v3/entity_resolution_base.parquet"

Path("data/processed/v3").mkdir(parents=True, exist_ok=True)

SHARED_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "linktr.ee",
    "yp.ca",
    "linkedin.com",
    "x.com",
    "twitter.com",
}

con = duckdb.connect()

shared_sql = ",".join(
    "'" + x.replace("'", "''") + "'"
    for x in SHARED_DOMAINS
)

con.execute(f"""
COPY (
    WITH prepared AS (
        SELECT
            *,

            split_part(
                regexp_replace(
                    regexp_replace(
                        lower(coalesce(website, '')),
                        '^https?://',
                        ''
                    ),
                    '^www\\\\.',
                    ''
                ),
                '/',
                1
            ) AS website_domain,

            regexp_replace(
                upper(coalesce(postal_code, '')),
                '[^A-Z0-9]',
                '',
                'g'
            ) AS normalized_postal,

            right(
                regexp_replace(
                    coalesce(phone, ''),
                    '[^0-9]',
                    '',
                    'g'
                ),
                10
            ) AS normalized_phone

        FROM read_parquet('{INPUT}')
    )

    SELECT
        *,

        CASE
            WHEN website_domain = ''
                THEN NULL

            WHEN website_domain IN ({shared_sql})
                THEN NULL

            ELSE website_domain
        END AS identity_domain,

        CASE
            WHEN website_domain IN ({shared_sql})
                THEN 'SHARED_PLATFORM_DOMAIN'

            WHEN website_domain <> ''
                THEN 'BUSINESS_OR_BRAND_DOMAIN'

            ELSE 'NO_DOMAIN'
        END AS domain_type,

        CASE
            WHEN normalized_name <> ''
             AND normalized_postal <> ''
                THEN normalized_name || '|P|' || normalized_postal

            WHEN normalized_name <> ''
             AND normalized_phone <> ''
                THEN normalized_name || '|T|' || normalized_phone

            WHEN normalized_name <> ''
             AND website_domain <> ''
             AND website_domain NOT IN ({shared_sql})
                THEN normalized_name || '|D|' || website_domain

            ELSE NULL
        END AS conservative_location_key,

        CASE
            WHEN normalized_name <> ''
             AND normalized_postal <> ''
                THEN 'NAME_POSTAL'

            WHEN normalized_name <> ''
             AND normalized_phone <> ''
                THEN 'NAME_PHONE'

            WHEN normalized_name <> ''
             AND website_domain <> ''
             AND website_domain NOT IN ({shared_sql})
                THEN 'NAME_DOMAIN'

            ELSE 'INSUFFICIENT_IDENTITY_EVIDENCE'
        END AS resolution_method

    FROM prepared
)
TO '{OUTPUT}'
(FORMAT PARQUET, COMPRESSION ZSTD)
""")

summary = con.execute(f"""
SELECT
    COUNT(*) AS total,

    COUNT(*) FILTER (
        WHERE resolution_method = 'NAME_POSTAL'
    ) AS name_postal,

    COUNT(*) FILTER (
        WHERE resolution_method = 'NAME_PHONE'
    ) AS name_phone,

    COUNT(*) FILTER (
        WHERE resolution_method = 'NAME_DOMAIN'
    ) AS name_domain,

    COUNT(*) FILTER (
        WHERE resolution_method =
              'INSUFFICIENT_IDENTITY_EVIDENCE'
    ) AS insufficient,

    COUNT(*) FILTER (
        WHERE domain_type = 'SHARED_PLATFORM_DOMAIN'
    ) AS shared_domains,

    COUNT(DISTINCT conservative_location_key)
        FILTER (
            WHERE conservative_location_key IS NOT NULL
        ) AS unique_keys

FROM read_parquet('{OUTPUT}')
""").fetchone()

print("\n=== V3 ENTITY RESOLUTION BASE ===\n")

print(f"Total locations       : {summary[0]:,}")
print(f"Name + postal         : {summary[1]:,}")
print(f"Name + phone fallback : {summary[2]:,}")
print(f"Name + domain fallback: {summary[3]:,}")
print(f"Insufficient evidence : {summary[4]:,}")
print(f"Shared-platform URLs  : {summary[5]:,}")
print(f"Unique location keys  : {summary[6]:,}")

print(f"\nSaved: {OUTPUT}")
print("\nDONE")