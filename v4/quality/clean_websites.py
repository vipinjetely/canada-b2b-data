from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT
    / "data"
    / "processed"
    / "v3"
    / "business_locations_scored.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "website_quality"
)

CLEAN_OUTPUT = (
    OUTPUT_DIR
    / "business_locations_websites_cleaned.parquet"
)

QUARANTINE_OUTPUT = (
    OUTPUT_DIR
    / "website_quarantine.parquet"
)

AUDIT_OUTPUT = (
    OUTPUT_DIR
    / "website_cleanup_audit.json"
)


# Domains that are useful as references/listings,
# but should NOT be treated as the company's own website.
BLOCKED_DOMAINS = [
    # Social platforms
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "tiktok.com",

    # Business directories
    "yellowpages.ca",
    "yellowpages.com",
    "yelp.ca",
    "yelp.com",
    "canpages.ca",
    "411.ca",
    "mapquest.com",
    "foursquare.com",

    # Search / map destinations
    "google.com",
    "google.ca",
    "goo.gl",

    # Canada Post
    "canadapost-postescanada.ca",
    "canadapost.ca",
]


def sql_path(path: Path) -> str:
    """
    Escape a filesystem path for embedding inside
    a DuckDB SQL string.
    """
    return str(path).replace("'", "''")


def domain_condition(domain_expression: str) -> str:
    """
    Build SQL condition matching both the root domain
    and any subdomain.

    Example:
        facebook.com
        www.facebook.com
        m.facebook.com
    """

    conditions = []

    for domain in BLOCKED_DOMAINS:

        safe_domain = domain.replace("'", "''")

        conditions.append(
            f"""
            (
                {domain_expression} = '{safe_domain}'
                OR
                {domain_expression} LIKE '%.{safe_domain}'
            )
            """
        )

    return " OR ".join(conditions)


def main() -> None:

    print("=== V4 WEBSITE QUALITY CLEANUP ===")
    print()

    # --------------------------------------------------
    # Preconditions
    # --------------------------------------------------

    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Source dataset not found: {SOURCE}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Avoid stale outputs from previous runs.
    for output_file in [
        CLEAN_OUTPUT,
        QUARANTINE_OUTPUT,
    ]:
        if output_file.exists():
            output_file.unlink()

    source_sql = sql_path(SOURCE)
    clean_sql = sql_path(CLEAN_OUTPUT)
    quarantine_sql = sql_path(QUARANTINE_OUTPUT)

    con = duckdb.connect()

    try:

        # --------------------------------------------------
        # STEP 1
        # Normalize the website host independently from
        # existing website_domain/domain_type columns.
        # --------------------------------------------------

        con.execute(
            f"""
            CREATE OR REPLACE TEMP VIEW website_audit AS

            SELECT
                *,

                CASE

                    WHEN website IS NULL
                         OR LENGTH(
                             TRIM(
                                 CAST(
                                     website AS VARCHAR
                                 )
                             )
                         ) = 0

                    THEN NULL

                    ELSE LOWER(
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                REGEXP_REPLACE(
                                    TRIM(
                                        CAST(
                                            website
                                            AS VARCHAR
                                        )
                                    ),
                                    '^https?://',
                                    ''
                                ),
                                '^www\\.',
                                ''
                            ),
                            '[/\\?#].*$',
                            ''
                        )
                    )

                END AS audit_website_host

            FROM read_csv_auto(
                '{source_sql}',
                HEADER = TRUE
            )
            """
        )

        # --------------------------------------------------
        # Baseline counts
        # --------------------------------------------------

        total_rows = con.execute(
            """
            SELECT COUNT(*)
            FROM website_audit
            """
        ).fetchone()[0]

        website_nonblank = con.execute(
            """
            SELECT COUNT(*)
            FROM website_audit
            WHERE audit_website_host IS NOT NULL
              AND LENGTH(
                    TRIM(audit_website_host)
                  ) > 0
            """
        ).fetchone()[0]

        blocked_condition = domain_condition(
            "audit_website_host"
        )

        # --------------------------------------------------
        # STEP 2
        # Quarantine rejected website values.
        #
        # IMPORTANT:
        # Business records are NOT deleted.
        # --------------------------------------------------

        con.execute(
            f"""
            COPY (

                SELECT
                    *,

                    CASE

                        WHEN (
                            audit_website_host = 'facebook.com'
                            OR audit_website_host LIKE '%.facebook.com'
                        )
                        THEN 'SOCIAL_FACEBOOK'

                        WHEN (
                            audit_website_host = 'instagram.com'
                            OR audit_website_host LIKE '%.instagram.com'
                        )
                        THEN 'SOCIAL_INSTAGRAM'

                        WHEN (
                            audit_website_host = 'linkedin.com'
                            OR audit_website_host LIKE '%.linkedin.com'
                        )
                        THEN 'SOCIAL_LINKEDIN'

                        WHEN (
                            audit_website_host = 'twitter.com'
                            OR audit_website_host LIKE '%.twitter.com'
                            OR audit_website_host = 'x.com'
                            OR audit_website_host LIKE '%.x.com'
                        )
                        THEN 'SOCIAL_X_TWITTER'

                        WHEN (
                            audit_website_host = 'youtube.com'
                            OR audit_website_host LIKE '%.youtube.com'
                        )
                        THEN 'SOCIAL_YOUTUBE'

                        WHEN (
                            audit_website_host = 'tiktok.com'
                            OR audit_website_host LIKE '%.tiktok.com'
                        )
                        THEN 'SOCIAL_TIKTOK'

                        WHEN (
                            audit_website_host = 'yellowpages.ca'
                            OR audit_website_host LIKE '%.yellowpages.ca'
                            OR audit_website_host = 'yellowpages.com'
                            OR audit_website_host LIKE '%.yellowpages.com'
                        )
                        THEN 'DIRECTORY_YELLOWPAGES'

                        WHEN (
                            audit_website_host = 'canadapost.ca'
                            OR audit_website_host LIKE '%.canadapost.ca'
                            OR audit_website_host = 'canadapost-postescanada.ca'
                            OR audit_website_host LIKE '%.canadapost-postescanada.ca'
                        )
                        THEN 'DIRECTORY_CANADA_POST'

                        WHEN (
                            audit_website_host = 'yelp.ca'
                            OR audit_website_host LIKE '%.yelp.ca'
                            OR audit_website_host = 'yelp.com'
                            OR audit_website_host LIKE '%.yelp.com'
                        )
                        THEN 'DIRECTORY_YELP'

                        WHEN (
                            audit_website_host = 'canpages.ca'
                            OR audit_website_host LIKE '%.canpages.ca'
                        )
                        THEN 'DIRECTORY_CANPAGES'

                        WHEN (
                            audit_website_host = '411.ca'
                            OR audit_website_host LIKE '%.411.ca'
                        )
                        THEN 'DIRECTORY_411'

                        WHEN (
                            audit_website_host = 'mapquest.com'
                            OR audit_website_host LIKE '%.mapquest.com'
                        )
                        THEN 'DIRECTORY_MAPQUEST'

                        WHEN (
                            audit_website_host = 'foursquare.com'
                            OR audit_website_host LIKE '%.foursquare.com'
                        )
                        THEN 'DIRECTORY_FOURSQUARE'

                        WHEN (
                            audit_website_host = 'google.com'
                            OR audit_website_host LIKE '%.google.com'
                            OR audit_website_host = 'google.ca'
                            OR audit_website_host LIKE '%.google.ca'
                            OR audit_website_host = 'goo.gl'
                            OR audit_website_host LIKE '%.goo.gl'
                        )
                        THEN 'SEARCH_OR_MAP_LISTING'

                        ELSE
                            'OTHER_DIRECTORY_OR_SOCIAL'

                    END AS website_rejection_reason,

                    CURRENT_TIMESTAMP
                        AS website_audited_at

                FROM website_audit

                WHERE
                    audit_website_host IS NOT NULL
                    AND (
                        {blocked_condition}
                    )

            )
            TO '{quarantine_sql}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        quarantined = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(QUARANTINE_OUTPUT)],
        ).fetchone()[0]

        # --------------------------------------------------
        # STEP 3
        # Produce cleaned dataset.
        #
        # Original website is retained for audit.
        # website_clean becomes NULL for rejected URLs.
        # --------------------------------------------------

        con.execute(
            f"""
            COPY (

                SELECT

                    * EXCLUDE (
                        audit_website_host
                    ),

                    CASE

                        WHEN audit_website_host IS NULL
                        THEN website

                        WHEN (
                            {blocked_condition}
                        )
                        THEN NULL

                        ELSE website

                    END AS website_clean,

                    CASE

                        WHEN audit_website_host IS NULL
                        THEN NULL

                        WHEN (
                            {blocked_condition}
                        )
                        THEN NULL

                        ELSE audit_website_host

                    END AS website_domain_clean,

                    CASE

                        WHEN audit_website_host IS NULL
                        THEN 'NO_WEBSITE'

                        WHEN (
                            {blocked_condition}
                        )
                        THEN
                            'QUARANTINED_DIRECTORY_OR_SOCIAL'

                        ELSE
                            'RETAINED_COMPANY_WEBSITE'

                    END AS website_quality_status,

                    CURRENT_TIMESTAMP
                        AS website_last_verified_at

                FROM website_audit

            )
            TO '{clean_sql}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        # --------------------------------------------------
        # STEP 4
        # Validate row preservation.
        # --------------------------------------------------

        cleaned_rows = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            """,
            [str(CLEAN_OUTPUT)],
        ).fetchone()[0]

        cleaned_nonblank = con.execute(
            """
            SELECT COUNT(*)
            FROM read_parquet(?)

            WHERE website_clean IS NOT NULL

              AND LENGTH(
                    TRIM(
                        CAST(
                            website_clean
                            AS VARCHAR
                        )
                    )
                  ) > 0
            """,
            [str(CLEAN_OUTPUT)],
        ).fetchone()[0]

        # --------------------------------------------------
        # STEP 5
        # Verify that none of the blocked domains survived
        # in website_domain_clean.
        # --------------------------------------------------

        clean_block_condition = domain_condition(
            "website_domain_clean"
        )

        blocked_remaining = con.execute(
            f"""
            SELECT COUNT(*)

            FROM read_parquet(?)

            WHERE
                website_domain_clean IS NOT NULL

                AND (
                    {clean_block_condition}
                )
            """,
            [str(CLEAN_OUTPUT)],
        ).fetchone()[0]

        # --------------------------------------------------
        # STEP 6
        # Rejection statistics.
        # --------------------------------------------------

        reason_counts = con.execute(
            """
            SELECT
                website_rejection_reason,
                COUNT(*) AS records

            FROM read_parquet(?)

            GROUP BY
                website_rejection_reason

            ORDER BY
                records DESC
            """,
            [str(QUARANTINE_OUTPUT)],
        ).fetchall()

        # --------------------------------------------------
        # Specifically count categories Karan flagged.
        # --------------------------------------------------

        karan_flagged = con.execute(
            """
            SELECT COUNT(*)

            FROM read_parquet(?)

            WHERE website_rejection_reason IN (
                'SOCIAL_FACEBOOK',
                'SOCIAL_INSTAGRAM',
                'DIRECTORY_YELLOWPAGES',
                'DIRECTORY_CANADA_POST'
            )
            """,
            [str(QUARANTINE_OUTPUT)],
        ).fetchone()[0]

        row_count_preserved = (
            total_rows == cleaned_rows
        )

    finally:
        con.close()

    # --------------------------------------------------
    # STEP 7
    # Build audit evidence.
    # --------------------------------------------------

    audit = {

        "built_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "source_file":
            str(SOURCE),

        "clean_output":
            str(CLEAN_OUTPUT),

        "quarantine_output":
            str(QUARANTINE_OUTPUT),

        "source_rows":
            total_rows,

        "cleaned_rows":
            cleaned_rows,

        "row_count_preserved":
            row_count_preserved,

        "website_nonblank_before":
            website_nonblank,

        "websites_quarantined":
            quarantined,

        "website_nonblank_after":
            cleaned_nonblank,

        "blocked_domains_remaining":
            blocked_remaining,

        "karan_specifically_flagged_categories":
            karan_flagged,

        "rejection_reason_counts": {
            reason: count
            for reason, count
            in reason_counts
        },

        "blocked_domain_roots":
            BLOCKED_DOMAINS,

        "methodology": {

            "business_records_deleted":
                False,

            "bad_website_handling":
                (
                    "Rejected website values are "
                    "quarantined and website_clean "
                    "is set to NULL. The business "
                    "record itself is retained."
                ),

            "original_website_preserved":
                True,

            "host_normalization":
                (
                    "Lowercase host; remove HTTP/HTTPS "
                    "scheme, leading www, path, query "
                    "string and fragment."
                ),

            "subdomains_blocked":
                True,

            "audit_evidence_preserved":
                True,
        },
    }

    AUDIT_OUTPUT.write_text(
        json.dumps(
            audit,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------
    # Final console report
    # --------------------------------------------------

    print(
        f"Source rows             : "
        f"{total_rows:,}"
    )

    print(
        f"Cleaned rows            : "
        f"{cleaned_rows:,}"
    )

    print(
        "Row count preserved     : "
        + (
            "YES"
            if row_count_preserved
            else "NO"
        )
    )

    print()

    print(
        f"Websites before         : "
        f"{website_nonblank:,}"
    )

    print(
        f"Quarantined             : "
        f"{quarantined:,}"
    )

    print(
        f"Websites after          : "
        f"{cleaned_nonblank:,}"
    )

    print(
        f"Blocked remaining       : "
        f"{blocked_remaining:,}"
    )

    print()

    print(
        f"Karan flagged categories: "
        f"{karan_flagged:,}"
    )

    print()
    print("Rejection reasons:")

    for reason, count in reason_counts:

        print(
            f"  {reason:<35} "
            f"{count:>10,}"
        )

    print()

    print(
        f"Clean output            : "
        f"{CLEAN_OUTPUT}"
    )

    print(
        f"Quarantine              : "
        f"{QUARANTINE_OUTPUT}"
    )

    print(
        f"Audit                   : "
        f"{AUDIT_OUTPUT}"
    )

    print()

    # --------------------------------------------------
    # Hard quality gates.
    # --------------------------------------------------

    if not row_count_preserved:

        raise RuntimeError(
            "CRITICAL: source row count "
            "was not preserved."
        )

    if blocked_remaining != 0:

        raise RuntimeError(
            "CRITICAL: blocked website "
            "domains remain in cleaned output."
        )

    print(
        "=== V4 WEBSITE QUALITY "
        "CLEANUP SUCCESS ==="
    )


if __name__ == "__main__":
    main()