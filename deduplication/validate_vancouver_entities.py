from pathlib import Path

import pandas as pd


ENTITY_PATH = Path(
    "data/processed/v2/entity_resolution/"
    "vancouver_local_entities.csv"
)

MEMBERS_PATH = Path(
    "data/processed/v2/entity_resolution/"
    "vancouver_entity_members.csv"
)

OUTPUT_PATH = Path(
    "data/processed/v2/entity_resolution/"
    "vancouver_local_entities_validated.csv"
)


def main():
    print("Reading Vancouver canonical entities...")

    entities = pd.read_csv(
        ENTITY_PATH,
        dtype="string",
        low_memory=False,
    )

    members = pd.read_csv(
        MEMBERS_PATH,
        dtype="string",
        low_memory=False,
    )

    print(f"Entities: {len(entities):,}")
    print(f"Source records: {len(members):,}")

    # -----------------------------------------
    # Basic integrity checks
    # -----------------------------------------

    if entities["local_entity_key"].duplicated().any():
        raise RuntimeError(
            "Duplicate local entity keys detected."
        )

    if members["source_record_id"].duplicated().any():
        raise RuntimeError(
            "Duplicate Vancouver source records detected."
        )

    unknown_keys = set(
        members["local_entity_key"].dropna()
    ) - set(
        entities["local_entity_key"].dropna()
    )

    if unknown_keys:
        raise RuntimeError(
            f"{len(unknown_keys):,} member entity keys "
            "do not exist in canonical entities."
        )

    # -----------------------------------------
    # Identity confidence
    # -----------------------------------------

    confidence_map = {
        "NAME_POSTAL_ADDRESS": 95,
        "NAME_CITY_ADDRESS": 90,
        "NAME_POSTAL": 85,
        "NAME_CITY": 70,
        "LICENCE_FALLBACK": 50,
    }

    entities["identity_confidence_score"] = (
        entities["identity_method"]
        .map(confidence_map)
        .astype("Int64")
    )

    entities["identity_quality"] = "REVIEW_REQUIRED"

    entities.loc[
        entities["identity_confidence_score"] >= 90,
        "identity_quality",
    ] = "HIGH_CONFIDENCE"

    entities.loc[
        entities["identity_confidence_score"].between(
            70, 89
        ),
        "identity_quality",
    ] = "MEDIUM_CONFIDENCE"

    # -----------------------------------------
    # Completeness / quality score
    # -----------------------------------------

    entities["has_name"] = (
        entities["display_name"].notna()
    )

    entities["has_address"] = (
        entities["street"].notna()
    )

    entities["has_city"] = (
        entities["city"].notna()
    )

    entities["has_postal"] = (
        entities["postal_code"].notna()
    )

    entities["has_industry"] = (
        entities["business_type"].notna()
    )

    entities["has_employee_count"] = (
        entities["employee_count"].notna()
    )

    entities["quality_score"] = (
        entities["has_name"].astype(int) * 25
        + entities["has_address"].astype(int) * 20
        + entities["has_city"].astype(int) * 10
        + entities["has_postal"].astype(int) * 15
        + entities["has_industry"].astype(int) * 15
        + entities["has_employee_count"].astype(int) * 15
    )

    # -----------------------------------------
    # New-business flags
    # Based on first issued date.
    # -----------------------------------------

    first_issued = pd.to_datetime(
        entities["first_issued_at"],
        errors="coerce",
        utc=True,
    )

    latest_extract = pd.to_datetime(
        entities["latest_extract_at"],
        errors="coerce",
        utc=True,
    )

    # Use dataset observation time rather than the
    # computer clock so results are reproducible.
    reference_time = latest_extract.max()

    if pd.isna(reference_time):
        raise RuntimeError(
            "Unable to determine Vancouver reference time."
        )

    age_days = (
        reference_time - first_issued
    ).dt.total_seconds() / 86400

    entities["is_new_1d"] = (
        first_issued.notna()
        & age_days.ge(0)
        & age_days.le(1)
    )

    entities["is_new_7d"] = (
        first_issued.notna()
        & age_days.ge(0)
        & age_days.le(7)
    )

    entities["is_new_30d"] = (
        first_issued.notna()
        & age_days.ge(0)
        & age_days.le(30)
    )

    entities["reference_time"] = (
        reference_time.isoformat()
    )

    # -----------------------------------------
    # Save
    # -----------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    entities.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print(
        "\n=== VANCOUVER ENTITY VALIDATION ==="
    )

    print(
        f"Validated entities: {len(entities):,}"
    )

    print("\nIdentity quality:")

    print(
        entities["identity_quality"]
        .value_counts()
        .to_string()
    )

    print("\nQuality-score distribution:")

    print(
        entities["quality_score"]
        .value_counts()
        .sort_index(ascending=False)
        .to_string()
    )

    print(
        "\nNew businesses:"
    )

    print(
        "Last 1 day: "
        f"{int(entities['is_new_1d'].sum()):,}"
    )

    print(
        "Last 7 days: "
        f"{int(entities['is_new_7d'].sum()):,}"
    )

    print(
        "Last 30 days: "
        f"{int(entities['is_new_30d'].sum()):,}"
    )

    print(
        "\nEmployee count available: "
        f"{int(entities['has_employee_count'].sum()):,}"
    )

    print(
        "Industry/business type available: "
        f"{int(entities['has_industry'].sum()):,}"
    )

    print(
        "\nReference time: "
        f"{reference_time}"
    )

    print(
        "\nNo database records were modified."
    )

    print(
        f"\nValidated output: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()