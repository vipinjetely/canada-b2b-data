from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed/v2")

RBQ_FILE = (
    PROCESSED_DIR
    / "quebec_rbq_licences_normalized.csv"
)

FEDERAL_FILE = (
    PROCESSED_DIR
    / "corporations_canada_normalized.csv"
)

OUTPUT_DIR = (
    PROCESSED_DIR
    / "entity_resolution"
)

LOCAL_ENTITIES_FILE = (
    OUTPUT_DIR
    / "quebec_rbq_local_entities.csv"
)

LOCAL_SOURCE_RECORDS_FILE = (
    OUTPUT_DIR
    / "quebec_rbq_local_source_records.csv"
)

FEDERAL_MATCHES_FILE = (
    OUTPUT_DIR
    / "quebec_rbq_federal_matches.csv"
)

REVIEW_FILE = (
    OUTPUT_DIR
    / "quebec_rbq_review.csv"
)


def clean_text(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return re.sub(r"\s+", " ", value)


def normalize_text(value):
    value = clean_text(value)

    if not value:
        return None

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = value.upper()

    value = re.sub(
        r"[^A-Z0-9]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def normalize_postal(value):
    value = clean_text(value)

    if not value:
        return None

    value = re.sub(
        r"[^A-Z0-9]",
        "",
        value.upper(),
    )

    if len(value) == 6:
        return value

    return None


def extract_postal_from_address(value):
    value = clean_text(value)

    if not value:
        return None

    match = re.search(
        r"\b([A-Z]\d[A-Z])[\s-]?(\d[A-Z]\d)\b",
        value.upper(),
    )

    if not match:
        return None

    return (
        match.group(1)
        + match.group(2)
    )


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "Reading Québec RBQ normalized records..."
    )

    rbq = pd.read_csv(
        RBQ_FILE,
        dtype=str,
        low_memory=False,
    )

    print(
        f"RBQ licence records: {len(rbq):,}"
    )

    print(
        "Reading Corporations Canada normalized records..."
    )

    federal = pd.read_csv(
        FEDERAL_FILE,
        dtype=str,
        low_memory=False,
    )

    print(
        f"Federal records: {len(federal):,}"
    )

    # -------------------------------------------------
    # RBQ preparation
    # -------------------------------------------------

    rbq["match_name"] = (
        rbq["legal_name"]
        .map(normalize_text)
    )

    rbq["match_operating_name"] = (
        rbq["operating_name"]
        .map(normalize_text)
    )

    rbq["match_city"] = (
        rbq["city"]
        .map(normalize_text)
    )

    rbq["match_postal"] = (
        rbq["address"]
        .map(extract_postal_from_address)
    )

    # -------------------------------------------------
    # Federal preparation
    # -------------------------------------------------

    federal["match_name"] = (
        federal["legal_name"]
        .map(normalize_text)
    )

    federal["match_city"] = (
        federal["city"]
        .map(normalize_text)
    )

    federal["match_postal"] = (
        federal["postal_code"]
        .map(normalize_postal)
    )

    # Only names that identify exactly one federal
    # corporation are eligible for automatic matching.
    federal_name_counts = (
        federal[
            federal["match_name"].notna()
        ]
        .groupby("match_name")
        .size()
    )

    unique_federal_names = set(
        federal_name_counts[
            federal_name_counts == 1
        ].index
    )

    federal_unique = (
        federal[
            federal["match_name"].isin(
                unique_federal_names
            )
        ]
        .copy()
    )

    federal_lookup = (
        federal_unique
        .set_index("match_name")
        .to_dict("index")
    )

    # -------------------------------------------------
    # Match each RBQ licence conservatively
    # -------------------------------------------------

    match_results = []

    for row in rbq.itertuples(
        index=False
    ):
        name = row.match_name

        result = {
            "source_record_id":
                row.source_record_id,

            "licence_number":
                row.licence_number,

            "neq":
                row.neq,

            "legal_name":
                row.legal_name,

            "operating_name":
                row.operating_name,

            "city":
                row.city,

            "address":
                row.address,

            "match_name":
                name,

            "match_city":
                row.match_city,

            "match_postal":
                row.match_postal,

            "federal_corporation_number":
                None,

            "match_category":
                None,
        }

        if (
            not name
            or name not in federal_lookup
        ):
            result[
                "match_category"
            ] = (
                "NO_FEDERAL_UNIQUE_NAME_MATCH"
            )

            match_results.append(result)
            continue

        fed = federal_lookup[name]

        fed_city = fed.get(
            "match_city"
        )

        fed_postal = fed.get(
            "match_postal"
        )

        same_city = bool(
            row.match_city
            and fed_city
            and row.match_city == fed_city
        )

        same_postal = bool(
            row.match_postal
            and fed_postal
            and row.match_postal == fed_postal
        )

        if same_city and same_postal:
            category = (
                "FEDERAL_NAME_POSTAL_CITY"
            )

        elif same_postal:
            category = (
                "FEDERAL_NAME_POSTAL"
            )

        elif same_city:
            category = (
                "FEDERAL_NAME_CITY_REVIEW"
            )

        else:
            category = (
                "FEDERAL_NAME_ONLY_REVIEW"
            )

        result[
            "federal_corporation_number"
        ] = fed.get(
            "federal_corporation_number"
        )

        result[
            "match_category"
        ] = category

        match_results.append(result)

    matches = pd.DataFrame(
        match_results
    )

    # Only postal-backed matches are automatic.
    strong_categories = {
        "FEDERAL_NAME_POSTAL_CITY",
        "FEDERAL_NAME_POSTAL",
    }

    strong = matches[
        matches["match_category"].isin(
            strong_categories
        )
    ].copy()

    review = matches[
        matches["match_category"].isin(
            {
                "FEDERAL_NAME_CITY_REVIEW",
                "FEDERAL_NAME_ONLY_REVIEW",
            }
        )
    ].copy()

    # Everything not strongly linked to Federal
    # remains eligible for Québec-local identity.
    strong_source_ids = set(
        strong["source_record_id"]
    )

    local_records = rbq[
        ~rbq[
            "source_record_id"
        ].isin(
            strong_source_ids
        )
    ].copy()

    # -------------------------------------------------
    # Build canonical Québec-local identity
    #
    # NEQ is the preferred provincial identifier.
    # For the tiny number without a valid NEQ,
    # use conservative fallback identities.
    # -------------------------------------------------

    def identity_key(row):
        neq = clean_text(row["neq"])

        if neq:
            return (
                "NEQ:"
                + neq
            )

        name = row["match_name"]
        city = row["match_city"]
        postal = row["match_postal"]

        if name and postal:
            return (
                "NAME_POSTAL:"
                + name
                + "|"
                + postal
            )

        if name and city:
            return (
                "NAME_CITY:"
                + name
                + "|"
                + city
            )

        return (
            "LICENCE:"
            + str(
                row["licence_number"]
            )
        )

    local_records[
        "canonical_identity_key"
    ] = local_records.apply(
        identity_key,
        axis=1,
    )

    def identity_method(key):
        if key.startswith("NEQ:"):
            return "NEQ"

        if key.startswith(
            "NAME_POSTAL:"
        ):
            return "NAME_POSTAL"

        if key.startswith(
            "NAME_CITY:"
        ):
            return "NAME_CITY"

        return "LICENCE_FALLBACK"

    local_records[
        "identity_method"
    ] = local_records[
        "canonical_identity_key"
    ].map(
        identity_method
    )

    # Pick one representative row for each
    # canonical local business.
    #
    # Prefer records with email/phone/address.
    local_records[
        "_completeness"
    ] = (
        local_records[
            [
                "email",
                "phone",
                "address",
                "operating_name",
            ]
        ]
        .notna()
        .sum(axis=1)
    )

    representatives = (
        local_records
        .sort_values(
            by=[
                "canonical_identity_key",
                "_completeness",
                "licence_number",
            ],
            ascending=[
                True,
                False,
                True,
            ],
        )
        .drop_duplicates(
            subset=[
                "canonical_identity_key"
            ],
            keep="first",
        )
        .copy()
    )

    licence_counts = (
        local_records
        .groupby(
            "canonical_identity_key"
        )
        .size()
        .rename("source_record_count")
    )

    representatives = (
        representatives
        .merge(
            licence_counts,
            left_on=(
                "canonical_identity_key"
            ),
            right_index=True,
            how="left",
        )
    )

    def confidence(method):
        if method == "NEQ":
            return (
                "HIGH_CONFIDENCE",
                100,
            )

        if method == "NAME_POSTAL":
            return (
                "HIGH_CONFIDENCE",
                85,
            )

        if method == "NAME_CITY":
            return (
                "MEDIUM_CONFIDENCE",
                65,
            )

        return (
            "REVIEW",
            55,
        )

    confidence_values = (
        representatives[
            "identity_method"
        ]
        .map(confidence)
    )

    representatives[
        "identity_confidence"
    ] = confidence_values.map(
        lambda value: value[0]
    )

    representatives[
        "quality_score"
    ] = confidence_values.map(
        lambda value: value[1]
    )

    # -------------------------------------------------
    # Save outputs
    # -------------------------------------------------

    strong.to_csv(
        FEDERAL_MATCHES_FILE,
        index=False,
        encoding="utf-8",
    )

    review.to_csv(
        REVIEW_FILE,
        index=False,
        encoding="utf-8",
    )

    local_records.drop(
        columns=["_completeness"],
        errors="ignore",
    ).to_csv(
        LOCAL_SOURCE_RECORDS_FILE,
        index=False,
        encoding="utf-8",
    )

    representatives.drop(
        columns=["_completeness"],
        errors="ignore",
    ).to_csv(
        LOCAL_ENTITIES_FILE,
        index=False,
        encoding="utf-8",
    )

    # -------------------------------------------------
    # Report
    # -------------------------------------------------

    categories = (
        matches[
            "match_category"
        ]
        .value_counts()
    )

    identity_counts = (
        representatives[
            "identity_method"
        ]
        .value_counts()
    )

    confidence_counts = (
        representatives[
            "identity_confidence"
        ]
        .value_counts()
    )

    print()
    print(
        "=== QUÉBEC RBQ ENTITY RESOLUTION ==="
    )

    print(
        f"Current licence records: {len(rbq):,}"
    )

    print(
        "Strong Federal matches: "
        f"{len(strong):,}"
    )

    print(
        "Federal review candidates: "
        f"{len(review):,}"
    )

    print(
        "Local candidate licence records: "
        f"{len(local_records):,}"
    )

    print(
        "Canonical Québec entities: "
        f"{len(representatives):,}"
    )

    print()
    print("Federal match categories:")

    for category, count in (
        categories.items()
    ):
        print(
            f"  {category}: {count:,}"
        )

    print()
    print("Local identity methods:")

    for method, count in (
        identity_counts.items()
    ):
        print(
            f"  {method}: {count:,}"
        )

    print()
    print("Identity confidence:")

    for level, count in (
        confidence_counts.items()
    ):
        print(
            f"  {level}: {count:,}"
        )

    print()
    print(
        "Local entities with email: "
        f"{representatives['email'].notna().sum():,}"
    )

    print(
        "Local entities with phone: "
        f"{representatives['phone'].notna().sum():,}"
    )

    print(
        "Local entities with address: "
        f"{representatives['address'].notna().sum():,}"
    )

    print()
    print(
        "Licence records collapsed into "
        "canonical local identities: "
        f"{len(local_records) - len(representatives):,}"
    )

    print()
    print(
        f"Local entities: {LOCAL_ENTITIES_FILE}"
    )

    print(
        "Local source records: "
        f"{LOCAL_SOURCE_RECORDS_FILE}"
    )

    print(
        "Strong Federal matches: "
        f"{FEDERAL_MATCHES_FILE}"
    )

    print(
        f"Review file: {REVIEW_FILE}"
    )

    print()
    print(
        "Québec RBQ entity resolution completed."
    )


if __name__ == "__main__":
    main()