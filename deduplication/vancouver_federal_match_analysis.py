
from pathlib import Path
import pandas as pd

VANCOUVER_PATH = Path(
    "data/processed/v2/vancouver_business_licences_normalized.csv"
)

FEDERAL_PATH = Path(
    "data/processed/v2/corporations_canada_normalized.csv"
)

OUTPUT_DIR = Path("data/processed/v2/match_analysis")


def clean(series):
    return (
        series.astype("string")
        .str.upper()
        .str.strip()
        .replace("", pd.NA)
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Reading Vancouver records...")

    van = pd.read_csv(
        VANCOUVER_PATH,
        dtype="string",
        low_memory=False,
    )

    # Only current, named records.
    van = van[
        van["is_current_usable"].str.lower().eq("true")
    ].copy()

    van["name_key"] = clean(
        van["normalized_business_name"]
    )

    van["postal_key"] = (
        clean(van["postal_code"])
        .str.replace(" ", "", regex=False)
    )

    van["city_key"] = clean(van["city"])

    van["address_key"] = clean(
        van["street_address"]
    )

    # Keep one record per exact licence RSN.
    # Different licences/locations are NOT collapsed.
    van = van.sort_values(
        ["source_record_id", "extract_at"],
        na_position="first",
    ).drop_duplicates(
        subset=["source_record_id"],
        keep="last",
    )

    print("Reading federal records...")

    fed = pd.read_csv(
        FEDERAL_PATH,
        dtype="string",
        low_memory=False,
        usecols=[
            "federal_corporation_number",
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

    fed["city_key"] = clean(fed["city"])

    fed["address_key"] = clean(fed["street"])

    # Count unique federal entities per matching key.
    # A key matching multiple corporations is ambiguous.
    fed_name_postal = (
        fed.dropna(subset=["name_key", "postal_key"])
        .groupby(["name_key", "postal_key"])
        ["federal_corporation_number"]
        .nunique()
        .rename("name_postal_candidates")
        .reset_index()
    )

    fed_name_city = (
        fed.dropna(subset=["name_key", "city_key"])
        .groupby(["name_key", "city_key"])
        ["federal_corporation_number"]
        .nunique()
        .rename("name_city_candidates")
        .reset_index()
    )

    fed_name = (
        fed.dropna(subset=["name_key"])
        .groupby("name_key")
        ["federal_corporation_number"]
        .nunique()
        .rename("name_only_candidates")
        .reset_index()
    )

    print("Comparing matching keys...")

    van = van.merge(
        fed_name_postal,
        on=["name_key", "postal_key"],
        how="left",
        validate="many_to_one",
    )

    van = van.merge(
        fed_name_city,
        on=["name_key", "city_key"],
        how="left",
        validate="many_to_one",
    )

    van = van.merge(
        fed_name,
        on="name_key",
        how="left",
        validate="many_to_one",
    )

    for column in [
        "name_postal_candidates",
        "name_city_candidates",
        "name_only_candidates",
    ]:
        van[column] = (
            van[column].fillna(0).astype(int)
        )

    # These are candidate categories, not verified merges.
    # Name + city alone is insufficient for automatic merging.
    high = (
        van["name_postal_candidates"].eq(1)
    )

    ambiguous_postal = (
        van["name_postal_candidates"].gt(1)
    )

    city_candidate = (
        ~high
        & ~ambiguous_postal
        & van["name_city_candidates"].gt(0)
    )

    name_only = (
        ~high
        & ~ambiguous_postal
        & ~city_candidate
        & van["name_only_candidates"].gt(0)
    )

    van["match_category"] = "NO_FEDERAL_NAME_MATCH"

    van.loc[
        name_only, "match_category"
    ] = "NAME_ONLY_REVIEW"

    van.loc[
        city_candidate, "match_category"
    ] = "NAME_CITY_REVIEW"

    van.loc[
        ambiguous_postal, "match_category"
    ] = "AMBIGUOUS_NAME_POSTAL"

    van.loc[
        high, "match_category"
    ] = "UNIQUE_NAME_POSTAL_CANDIDATE"

    # A separate location key helps reveal repeat licences.
    van["location_key"] = (
        van["name_key"].fillna("")
        + "|"
        + van["postal_key"].fillna("")
        + "|"
        + van["address_key"].fillna("")
    )

    output_path = (
        OUTPUT_DIR / "vancouver_federal_candidates.csv"
    )

    van.to_csv(output_path, index=False)

    print("\n=== VANCOUVER ↔ FEDERAL ANALYSIS ===")
    print(f"Usable licence records: {len(van):,}")
    print(
        "Unique normalized names: "
        f"{van['name_key'].nunique():,}"
    )
    print(
        "Unique name/location keys: "
        f"{van['location_key'].nunique():,}"
    )

    print("\nMatching categories:")

    print(
        van["match_category"]
        .value_counts()
        .to_string()
    )

    print(
        "\nIMPORTANT: No federal matches have "
        "been automatically merged."
    )

    print(f"\nReport: {output_path}")


if __name__ == "__main__":
    main()