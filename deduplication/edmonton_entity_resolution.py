from pathlib import Path
import re

import pandas as pd


EDMONTON_FILE = Path(
    "data/processed/v2/edmonton_business_licences_normalized.csv"
)

FEDERAL_FILE = Path(
    "data/processed/v2/corporations_canada_normalized.csv"
)

OUT_DIR = Path(
    "data/processed/v2/entity_resolution"
)

ENTITY_FILE = OUT_DIR / "edmonton_local_entities.csv"
MEMBER_FILE = OUT_DIR / "edmonton_entity_members.csv"
MATCH_FILE = OUT_DIR / "edmonton_federal_matches.csv"


def clean(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def normalize_text(value):
    value = clean(value)

    if value is None:
        return None

    return re.sub(
        r"[^A-Z0-9]+",
        "",
        value.upper(),
    )


def normalize_address(value):
    value = clean(value)

    if value is None:
        return None

    value = value.upper()

    replacements = {
        " STREET": " ST",
        " AVENUE": " AVE",
        " ROAD": " RD",
        " DRIVE": " DR",
        " BOULEVARD": " BLVD",
        " TRAIL": " TRL",
        " HIGHWAY": " HWY",
        " SUITE ": " ",
        " UNIT ": " ",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return re.sub(r"[^A-Z0-9]+", "", value)


def bool_value(value):
    if pd.isna(value):
        return False

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "t",
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Reading Edmonton normalized data...")

    edmonton = pd.read_csv(
        EDMONTON_FILE,
        dtype="string",
        low_memory=False,
    )

    print(f"Edmonton licences: {len(edmonton):,}")

    print("Reading Federal normalized data...")

    federal = pd.read_csv(
        FEDERAL_FILE,
        dtype="string",
        low_memory=False,
    )

    # ----------------------------------------
    # Federal lookup
    # ----------------------------------------

    federal["match_name"] = (
        federal["legal_name"]
        .map(normalize_text)
        .fillna("")
    )

    federal["match_city"] = (
        federal["normalized_city"]
        .fillna("")
        .str.upper()
        .str.strip()
    )

    federal["match_address"] = (
        federal["street"]
        .map(normalize_address)
        .fillna("")
    )

    # A name must identify exactly one Federal
    # corporation before it can be considered
    # for automatic matching.
    name_counts = (
        federal[
            federal["match_name"] != ""
        ]
        .groupby("match_name")
        .size()
    )

    unique_names = set(
        name_counts[
            name_counts == 1
        ].index
    )

    fed_unique = (
        federal[
            federal["match_name"].isin(
                unique_names
            )
        ]
        .drop_duplicates(
            subset=["match_name"]
        )
        .set_index("match_name")
    )

    # ----------------------------------------
    # Edmonton matching fields
    # ----------------------------------------

    edmonton["match_name"] = (
        edmonton["legal_name"]
        .map(normalize_text)
        .fillna("")
    )

    edmonton["match_address"] = (
        edmonton["street"]
        .map(normalize_address)
        .fillna("")
    )

    categories = []
    matched_numbers = []

    print(
        "Comparing Edmonton against Federal master..."
    )

    for row in edmonton.itertuples(index=False):

        name = clean(row.match_name)
        address = clean(row.match_address)

        category = "NO_FEDERAL_UNIQUE_NAME_MATCH"
        federal_number = None

        if name and name in fed_unique.index:

            fed = fed_unique.loc[name]

            federal_number = clean(
                fed["federal_corporation_number"]
            )

            fed_city = clean(
                fed["match_city"]
            )

            fed_address = clean(
                fed["match_address"]
            )

            # Edmonton source itself establishes
            # Edmonton as the licensed operating city.
            # Federal city must also be Edmonton for
            # an address-based automatic merge.
            city_match = (
                fed_city == "EDMONTON"
            )

            address_match = (
                bool(address)
                and bool(fed_address)
                and address == fed_address
            )

            if city_match and address_match:
                category = (
                    "FEDERAL_NAME_CITY_ADDRESS"
                )

            elif city_match:
                category = (
                    "FEDERAL_NAME_CITY_REVIEW"
                )

            else:
                category = (
                    "FEDERAL_NAME_ONLY_REVIEW"
                )

        categories.append(category)
        matched_numbers.append(federal_number)

    edmonton["federal_match_category"] = categories

    edmonton[
        "matched_federal_number"
    ] = matched_numbers

    # Only exact unique-name + Edmonton city +
    # normalized-address matches are automatic.
    strong_categories = {
        "FEDERAL_NAME_CITY_ADDRESS"
    }

    edmonton["is_strong_federal_match"] = (
        edmonton[
            "federal_match_category"
        ].isin(strong_categories)
    )

    # ----------------------------------------
    # Build local candidates
    # ----------------------------------------

    local = edmonton[
        ~edmonton["is_strong_federal_match"]
    ].copy()

    # Do NOT collapse weak Federal review matches
    # into Federal corporations. They remain local
    # operating entities unless stronger evidence
    # becomes available later.

    local["identity_name"] = (
        local["normalized_legal_name"]
        .fillna("")
    )

    local["identity_address"] = (
        local["match_address"]
        .fillna("")
    )

    def build_identity(row):
        name = clean(row["identity_name"])
        address = clean(row["identity_address"])

        if name and address:
            return (
                f"NAME_ADDRESS|{name}|{address}",
                "NAME_ADDRESS",
                95,
            )

        if name:
            return (
                f"NAME_CITY|{name}|EDMONTON",
                "NAME_CITY",
                70,
            )

        return (
            "LICENCE|"
            + str(row["source_record_id"]),
            "LICENCE_FALLBACK",
            50,
        )

    identities = local.apply(
        build_identity,
        axis=1,
        result_type="expand",
    )

    identities.columns = [
        "local_entity_key",
        "identity_method",
        "identity_confidence_score",
    ]

    local = pd.concat(
        [
            local.reset_index(drop=True),
            identities.reset_index(drop=True),
        ],
        axis=1,
    )

    # ----------------------------------------
    # Canonical entity aggregation
    # ----------------------------------------

    local["most_recent_issue_date_dt"] = (
        pd.to_datetime(
            local["most_recent_issue_date"],
            errors="coerce",
            utc=True,
        )
    )

    local["original_issue_date_dt"] = (
        pd.to_datetime(
            local["original_issue_date"],
            errors="coerce",
            utc=True,
        )
    )

    local["source_updated_at_dt"] = (
        pd.to_datetime(
            local["source_updated_at"],
            errors="coerce",
            utc=True,
        )
    )

    local["expiry_date_dt"] = pd.to_datetime(
        local["expiry_date"],
        errors="coerce",
        utc=True,
    )

    local = local.sort_values(
        [
            "local_entity_key",
            "most_recent_issue_date_dt",
        ],
        na_position="first",
    )

    canonical = (
        local
        .groupby(
            "local_entity_key",
            as_index=False,
        )
        .agg(
            legal_name=("legal_name", "last"),
            operating_name=(
                "operating_name",
                "last",
            ),
            normalized_legal_name=(
                "normalized_legal_name",
                "last",
            ),
            street=("street", "last"),
            city=("city", "last"),
            province=("province", "last"),
            country=("country", "last"),
            postal_code=("postal_code", "last"),
            industry=("industry", "last"),
            licence_type=("licence_type", "last"),
            neighbourhood=(
                "neighbourhood",
                "last",
            ),
            ward=("ward", "last"),
            first_issued_at=(
                "original_issue_date_dt",
                "min",
            ),
            latest_issue_at=(
                "most_recent_issue_date_dt",
                "max",
            ),
            latest_expiry_at=(
                "expiry_date_dt",
                "max",
            ),
            latest_source_update_at=(
                "source_updated_at_dt",
                "max",
            ),
            licence_count=(
                "source_record_id",
                "nunique",
            ),
            identity_method=(
                "identity_method",
                "first",
            ),
            identity_confidence_score=(
                "identity_confidence_score",
                "first",
            ),
        )
    )

    # ----------------------------------------
    # Deterministic quality score
    # ----------------------------------------

    canonical["quality_score"] = 0

    canonical.loc[
        canonical["legal_name"].notna(),
        "quality_score",
    ] += 35

    canonical.loc[
        canonical["street"].notna(),
        "quality_score",
    ] += 25

    canonical.loc[
        canonical["industry"].notna(),
        "quality_score",
    ] += 20

    canonical.loc[
        canonical["latest_expiry_at"].notna(),
        "quality_score",
    ] += 10

    canonical.loc[
        canonical["first_issued_at"].notna(),
        "quality_score",
    ] += 10

    canonical["identity_quality"] = "REVIEW_REQUIRED"

    canonical.loc[
        canonical[
            "identity_confidence_score"
        ] >= 90,
        "identity_quality",
    ] = "HIGH_CONFIDENCE"

    canonical.loc[
        canonical[
            "identity_confidence_score"
        ].between(70, 89),
        "identity_quality",
    ] = "MEDIUM_CONFIDENCE"

    # ----------------------------------------
    # New-business signals
    # Preserve the source-derived flags.
    # ----------------------------------------

    new_flags = (
        local.groupby(
            "local_entity_key",
            as_index=False,
        )
        .agg(
            is_new_1d=("is_new_1d", lambda x: any(
                bool_value(v) for v in x
            )),
            is_new_7d=("is_new_7d", lambda x: any(
                bool_value(v) for v in x
            )),
            is_new_30d=("is_new_30d", lambda x: any(
                bool_value(v) for v in x
            )),
        )
    )

    canonical = canonical.merge(
        new_flags,
        on="local_entity_key",
        how="left",
    )

    # ----------------------------------------
    # Member/provenance output
    # ----------------------------------------

    member_columns = [
        "local_entity_key",
        "source_key",
        "source_record_id",
        "legal_name",
        "operating_name",
        "street",
        "city",
        "province",
        "country",
        "industry",
        "licence_type",
        "neighbourhood",
        "ward",
        "original_issue_date",
        "most_recent_issue_date",
        "expiry_date",
        "source_updated_at",
        "collected_at_utc",
        "federal_match_category",
        "matched_federal_number",
    ]

    members = local[
        [
            col
            for col in member_columns
            if col in local.columns
        ]
    ].copy()

    # ----------------------------------------
    # Save
    # ----------------------------------------

    canonical.to_csv(
        ENTITY_FILE,
        index=False,
    )

    members.to_csv(
        MEMBER_FILE,
        index=False,
    )

    edmonton.to_csv(
        MATCH_FILE,
        index=False,
    )

    strong_count = int(
        edmonton[
            "is_strong_federal_match"
        ].sum()
    )

    print(
        "\n=== EDMONTON ENTITY RESOLUTION ==="
    )

    print(
        f"Current licence records: "
        f"{len(edmonton):,}"
    )

    print(
        f"Strong federal matches: "
        f"{strong_count:,}"
    )

    print(
        f"Local candidate licence records: "
        f"{len(local):,}"
    )

    print(
        f"Canonical Edmonton entities: "
        f"{len(canonical):,}"
    )

    print("\nFederal match categories:")

    print(
        edmonton[
            "federal_match_category"
        ].value_counts()
    )

    print("\nIdentity quality:")

    print(
        canonical[
            "identity_quality"
        ].value_counts()
    )

    print(
        "\nEntities with visible address: "
        f"{canonical['street'].notna().sum():,}"
    )

    print(
        "New 7 days: "
        f"{canonical['is_new_7d'].sum():,}"
    )

    print(
        "New 30 days: "
        f"{canonical['is_new_30d'].sum():,}"
    )

    print(
        "\nEntities: "
        f"{ENTITY_FILE}"
    )

    print(
        "Members: "
        f"{MEMBER_FILE}"
    )

    print(
        "Match report: "
        f"{MATCH_FILE}"
    )

    print(
        "\nNo database records were modified."
    )


if __name__ == "__main__":
    main()