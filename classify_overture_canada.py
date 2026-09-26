from pathlib import Path
import duckdb

FILES = [
    "overture_ontario_raw.parquet",
    "overture_western_canada_raw.parquet",
    "overture_eastern_canada_raw.parquet",
    "overture_northern_canada_raw.parquet",
]

OUTPUT_DIR = Path("data/processed/v3")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "overture_canada_classified.parquet"

# Categories that are clearly geographic / non-business POIs.
# Keep this deliberately conservative: uncertain categories go to REVIEW.
NON_BUSINESS_CATEGORIES = {
    "lake",
    "river",
    "beach",
    "mountain",
    "waterfall",
    "island",
    "canal",
    "nature_reserve",
    "national_park",
    "recreational_trail_or_path",
    "historic_site",
    "cemetery",
    "garden",
    "lighthouse",
    "park",
}

con = duckdb.connect()

file_list_sql = ", ".join(f"'{f}'" for f in FILES)

non_business_sql = ", ".join(
    f"'{category}'" for category in sorted(NON_BUSINESS_CATEGORIES)
)

print("Loading Canadian Overture Places...")

con.execute(
    f"""
    CREATE OR REPLACE TEMP TABLE canada_places AS
    SELECT *
    FROM read_parquet([{file_list_sql}])
    WHERE addresses[1].country = 'CA'
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY id
        ORDER BY confidence DESC NULLS LAST
    ) = 1
    """
)

total = con.execute(
    "SELECT COUNT(*) FROM canada_places"
).fetchone()[0]

print(f"Unique Canadian Places: {total:,}")

print("Classifying records...")

con.execute(
    f"""
    CREATE OR REPLACE TEMP TABLE classified AS
    SELECT
        id,
        names.primary AS business_name,
        basic_category,
        confidence,
        operating_status,

        addresses[1].freeform AS address,
        addresses[1].locality AS city,
        addresses[1].region AS province,
        addresses[1].postcode AS postal_code,
        addresses[1].country AS country,

        CASE
            WHEN array_length(phones) > 0
                THEN phones[1]
            ELSE NULL
        END AS phone,

        CASE
            WHEN array_length(emails) > 0
                THEN emails[1]
            ELSE NULL
        END AS email,

        CASE
            WHEN array_length(websites) > 0
                THEN websites[1]
            ELSE NULL
        END AS website,

        CASE
            WHEN operating_status = 'permanently_closed'
                THEN 'NON_BUSINESS'

            WHEN basic_category IN ({non_business_sql})
                THEN 'NON_BUSINESS'

            WHEN basic_category IS NULL
                THEN 'REVIEW'

            ELSE 'BUSINESS'
        END AS classification,

        CASE
            WHEN operating_status = 'open'
                THEN 'CONFIRMED_OPEN'

            WHEN operating_status = 'temporarily_closed'
                THEN 'TEMPORARILY_CLOSED'

            WHEN operating_status = 'permanently_closed'
                THEN 'PERMANENTLY_CLOSED'

            ELSE 'STATUS_UNKNOWN'
        END AS operating_status_class

    FROM canada_places
    """
)

print("\nCLASSIFICATION SUMMARY")
print("----------------------")

summary = con.execute(
    """
    SELECT
        classification,
        COUNT(*) AS records,
        COUNT(phone) AS with_phone,
        COUNT(email) AS with_email,
        COUNT(website) AS with_website,
        ROUND(AVG(confidence), 3) AS avg_confidence
    FROM classified
    GROUP BY classification
    ORDER BY records DESC
    """
).fetchall()

for row in summary:
    print(
        f"{row[0]:15} "
        f"Records: {row[1]:,} | "
        f"Phone: {row[2]:,} | "
        f"Email: {row[3]:,} | "
        f"Website: {row[4]:,} | "
        f"Avg confidence: {row[5]}"
    )

print("\nOPERATING STATUS — BUSINESS CANDIDATES")
print("--------------------------------------")

status_rows = con.execute(
    """
    SELECT
        operating_status_class,
        COUNT(*)
    FROM classified
    WHERE classification = 'BUSINESS'
    GROUP BY operating_status_class
    ORDER BY COUNT(*) DESC
    """
).fetchall()

for status, count in status_rows:
    print(f"{status:25} {count:,}")

print("\nTOP BUSINESS CATEGORIES")
print("-----------------------")

categories = con.execute(
    """
    SELECT
        basic_category,
        COUNT(*) AS records
    FROM classified
    WHERE classification = 'BUSINESS'
    GROUP BY basic_category
    ORDER BY records DESC
    LIMIT 30
    """
).fetchall()

for category, count in categories:
    print(f"{str(category):45} {count:,}")

print("\nSaving classified dataset...")

con.execute(
    f"""
    COPY (
        SELECT *
        FROM classified
    )
    TO '{OUTPUT_FILE.as_posix()}'
    (FORMAT PARQUET, COMPRESSION ZSTD)
    """
)

print(f"\nSaved: {OUTPUT_FILE}")
print("DONE")