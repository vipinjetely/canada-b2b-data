from pathlib import Path
import re

import pandas as pd


CANDIDATE_PATH = Path(
    "data/processed/v2/match_analysis/"
    "vancouver_federal_candidates.csv"
)

FEDERAL_PATH = Path(
    "data/processed/v2/corporations_canada_normalized.csv"
)

OUTPUT_PATH = Path(
    "data/processed/v2/match_analysis/"
    "vancouver_federal_verified.csv"
)


def clean(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.upper()
        .str.strip()
        .replace("", pd.NA)
    )


def normalize_address(value):
    if pd.isna(value):
        return pd.NA

    text = str(value).upper().strip()

    # Remove punctuation but preserve numbers/letters.
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text or pd.NA


def main():
    print("Reading Vancouver candidate report...")

    van = pd.read_csv(
        CANDIDATE_PATH,
        dtype="string",
        low_memory=False,
    )

    van = van[
        van["match_category"].eq(
            "UNIQUE_NAME_POSTAL_CANDIDATE"
        )
    ].copy()

    print(
        f"Strong candidates found: {len(van):,}"
    )

    print("Reading federal records...")

    fed = pd.read_csv(
        FEDERAL_PATH,
        dtype="string",
        low_memory=False,
        usecols=[
            "federal_corporation_number",
            "legal_name",
            "normalized_legal_name",
            "postal_code",
            "city",
            "street",
        ],
    )

    fed["name_key"] = clean(
        fed["normalized_legal_name"]
    )

    fed["postal_key"] = (
        clean(fed["postal_code"])
        .str.replace(" ", "", regex=False)
    )

    fed["federal_city"] = clean(
        fed["city"]
    )

    fed["federal_address_normalized"] = (
        fed["street"].map(normalize_address)
    )

    # Only retain federal keys that point to exactly one
    # corporation.
    key_counts = (
        fed.dropna(
            subset=["name_key", "postal_key"]
        )
        .groupby(
            ["name_key", "postal_key"]
        )["federal_corporation_number"]
        .nunique()
        .rename("candidate_count")
        .reset_index()
    )

    unique_keys = key_counts[
        key_counts["candidate_count"].eq(1)
    ][["name_key", "postal_key"]]

    fed_unique = fed.merge(
        unique_keys,
        on=["name_key", "postal_key"],
        how="inner",
        validate="many_to_one",
    )

    # Defensive check: one row per unique key.
    fed_unique = fed_unique.sort_values(
        "federal_corporation_number"
    ).drop_duplicates(
        subset=["name_key", "postal_key"],
        keep="first",
    )

    van["vancouver_address_normalized"] = (
        van["address_key"].map(
            normalize_address
        )
    )

    print(
        "Attaching federal corporation records..."
    )

    matched = van.merge(
        fed_unique[
            [
                "name_key",
                "postal_key",
                "federal_corporation_number",
                "legal_name",
                "federal_city",
                "federal_address_normalized",
            ]
        ],
        on=["name_key", "postal_key"],
        how="left",
        validate="many_to_one",
    )

    if matched[
        "federal_corporation_number"
    ].isna().any():
        raise RuntimeError(
            "A supposedly unique federal candidate "
            "could not be attached."
        )

    matched["city_agrees"] = (
        matched["city_key"].notna()
        & matched["federal_city"].notna()
        & matched["city_key"].eq(
            matched["federal_city"]
        )
    )

    matched["exact_address_agrees"] = (
        matched[
            "vancouver_address_normalized"
        ].notna()
        & matched[
            "federal_address_normalized"
        ].notna()
        & matched[
            "vancouver_address_normalized"
        ].eq(
            matched[
                "federal_address_normalized"
            ]
        )
    )

    # Classification is deliberately conservative.
    #
    # Postal + name is already strong evidence.
    # Exact address provides additional confirmation.
    # City agreement is useful secondary evidence.
    matched["verification_category"] = (
        "NAME_POSTAL_ONLY_REVIEW"
    )

    matched.loc[
        matched["city_agrees"],
        "verification_category",
    ] = "NAME_POSTAL_CITY"

    matched.loc[
        matched["exact_address_agrees"],
        "verification_category",
    ] = "NAME_POSTAL_EXACT_ADDRESS"

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    matched.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print(
        "\n=== STRONG MATCH VERIFICATION ==="
    )

    print(
        f"Candidates analysed: {len(matched):,}"
    )

    print(
        "Unique federal corporations: "
        f"{matched['federal_corporation_number'].nunique():,}"
    )

    print(
        "\nVerification categories:"
    )

    print(
        matched["verification_category"]
        .value_counts()
        .to_string()
    )

    print(
        "\nExact address agreement: "
        f"{int(matched['exact_address_agrees'].sum()):,}"
    )

    print(
        "City agreement: "
        f"{int(matched['city_agrees'].sum()):,}"
    )

    print(
        "\nNo database records were modified."
    )

    print(
        f"\nReport: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()