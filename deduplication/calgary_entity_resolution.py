from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


CALGARY_FILE = Path(
    "data/processed/v2/calgary_business_licences_normalized.csv"
)
FEDERAL_FILE = Path(
    "data/processed/v2/corporations_canada_normalized.csv"
)

OUTPUT_DIR = Path("data/processed/v2/entity_resolution")

ENTITIES_FILE = OUTPUT_DIR / "calgary_local_entities.csv"
MEMBERS_FILE = OUTPUT_DIR / "calgary_entity_members.csv"
MATCHES_FILE = OUTPUT_DIR / "calgary_federal_matches.csv"


def normalize_text(value) -> str:
    if pd.isna(value):
        return ""

    value = str(value).strip().upper()
    value = re.sub(r"[^A-Z0-9]+", "", value)
    return value


def normalize_address(value) -> str:
    value = normalize_text(value)

    replacements = {
        "STREET": "ST",
        "AVENUE": "AV",
        "ROAD": "RD",
        "DRIVE": "DR",
        "BOULEVARD": "BLVD",
        "TRAIL": "TR",
        "HIGHWAY": "HWY",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return value


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Reading Calgary normalized data...")

    calgary = pd.read_csv(
        CALGARY_FILE,
        dtype=str,
        keep_default_na=False,
    )

    print(f"Calgary licences: {len(calgary):,}")

    print("Reading Federal normalized data...")

    federal = pd.read_csv(
        FEDERAL_FILE,
        dtype=str,
        keep_default_na=False,
    )

    # IMPORTANT:
    # Recompute both sides using exactly the same normalization.
    calgary["match_name"] = calgary["legal_name"].map(normalize_text)
    federal["match_name"] = federal["legal_name"].map(normalize_text)

    calgary["match_address"] = calgary["street"].map(normalize_address)
    federal["match_address"] = federal["street"].map(normalize_address)

    federal["match_city"] = federal["city"].map(normalize_text)

    # Only Federal names that occur exactly once are eligible for
    # automatic matching.
    federal_name_counts = federal["match_name"].value_counts()

    unique_federal_names = set(
        federal_name_counts[
            federal_name_counts == 1
        ].index
    )

    federal_unique = (
        federal[
            federal["match_name"].isin(unique_federal_names)
        ]
        .drop_duplicates("match_name")
        .set_index("match_name")
    )

    print("Comparing Calgary against Federal master...")

    match_rows = []

    for row in calgary.itertuples(index=False):
        name = row.match_name
        address = row.match_address

        category = "NO_FEDERAL_UNIQUE_NAME_MATCH"
        federal_number = ""

        if name and name in federal_unique.index:
            federal_row = federal_unique.loc[name]

            federal_number = str(
                federal_row.get("federal_corporation_number", "")
            ).strip()

            federal_city = normalize_text(
                federal_row.get("city", "")
            )

            federal_address = normalize_address(
                federal_row.get("street", "")
            )

            if (
                federal_city == "CALGARY"
                and address
                and federal_address
                and address == federal_address
            ):
                category = "FEDERAL_NAME_CITY_ADDRESS"

            elif federal_city == "CALGARY":
                category = "FEDERAL_NAME_CITY_REVIEW"

            else:
                category = "FEDERAL_NAME_ONLY_REVIEW"

        match_rows.append(
            {
                "source_record_id": row.source_record_id,
                "legal_name": row.legal_name,
                "street": row.street,
                "federal_corporation_number": federal_number,
                "federal_match_category": category,
            }
        )

    matches = pd.DataFrame(match_rows)

    strong_ids = set(
        matches.loc[
            matches["federal_match_category"]
            == "FEDERAL_NAME_CITY_ADDRESS",
            "source_record_id",
        ]
    )

    local = calgary[
        ~calgary["source_record_id"].isin(strong_ids)
    ].copy()

    # Canonical local identity:
    # name + visible address = strong local identity.
    # If no usable address, fall back to name + city.
    local["canonical_key"] = ""

    has_address = local["match_address"].ne("")

    local.loc[
        has_address,
        "canonical_key",
    ] = (
        "NAME_ADDRESS|"
        + local.loc[has_address, "match_name"]
        + "|"
        + local.loc[has_address, "match_address"]
    )

    local.loc[
        ~has_address,
        "canonical_key",
    ] = (
        "NAME_CITY|"
        + local.loc[~has_address, "match_name"]
        + "|CALGARY"
    )

    local["identity_quality"] = "MEDIUM_CONFIDENCE"
    local["identity_confidence"] = 70

    local.loc[
        has_address,
        "identity_quality",
    ] = "HIGH_CONFIDENCE"

    local.loc[
        has_address,
        "identity_confidence",
    ] = 95

    # Keep one canonical entity per identity key.
    entities = (
        local.sort_values(
            ["canonical_key", "expiry_date"],
            na_position="first",
        )
        .drop_duplicates(
            subset=["canonical_key"],
            keep="last",
        )
        .copy()
    )

    # Aggregate newness across all licences belonging to an entity.
    bool_columns = [
        "is_new_1d",
        "is_new_7d",
        "is_new_30d",
    ]

    for column in bool_columns:
        local[column] = (
            local[column]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin({"true", "1", "yes"})
        )

    newness = (
        local.groupby("canonical_key", as_index=False)[
            bool_columns
        ]
        .max()
    )

    entities = entities.drop(
        columns=bool_columns,
        errors="ignore",
    ).merge(
        newness,
        on="canonical_key",
        how="left",
    )

    members = local[
        [
            "source_record_id",
            "canonical_key",
            "legal_name",
            "street",
            "industry",
            "status",
            "first_issue_date",
            "expiry_date",
            "source_key",
            "collected_at_utc",
            "source_sha256",
        ]
    ].copy()

    entity_columns = [
        "canonical_key",
        "legal_name",
        "operating_name",
        "normalized_legal_name",
        "street",
        "city",
        "province",
        "country",
        "postal_code",
        "industry",
        "community_code",
        "community_name",
        "status",
        "first_issue_date",
        "expiry_date",
        "identity_quality",
        "identity_confidence",
        "source_key",
        "collected_at_utc",
        "source_sha256",
        "is_new_1d",
        "is_new_7d",
        "is_new_30d",
    ]

    entities[entity_columns].to_csv(
        ENTITIES_FILE,
        index=False,
    )

    members.to_csv(
        MEMBERS_FILE,
        index=False,
    )

    matches.to_csv(
        MATCHES_FILE,
        index=False,
    )

    print()
    print("=== CALGARY ENTITY RESOLUTION ===")
    print(f"Current licence records: {len(calgary):,}")
    print(f"Strong federal matches: {len(strong_ids):,}")
    print(f"Local candidate licence records: {len(local):,}")
    print(f"Canonical Calgary entities: {len(entities):,}")

    print()
    print("Federal match categories:")
    print(
        matches["federal_match_category"]
        .value_counts()
    )

    print()
    print("Identity quality:")
    print(
        entities["identity_quality"]
        .value_counts()
    )

    print(
        "\nEntities with visible address: "
        f"{entities['street'].ne('').sum():,}"
    )

    print(
        f"New 7 days: "
        f"{entities['is_new_7d'].sum():,}"
    )

    print(
        f"New 30 days: "
        f"{entities['is_new_30d'].sum():,}"
    )

    print()
    print(f"Entities: {ENTITIES_FILE}")
    print(f"Members: {MEMBERS_FILE}")
    print(f"Match report: {MATCHES_FILE}")

    print()
    print("No database records were modified.")


if __name__ == "__main__":
    main()