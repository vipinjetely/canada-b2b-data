from pathlib import Path
import hashlib

import pandas as pd


TORONTO_PATH = Path(
    "data/processed/v2/"
    "toronto_business_licences_normalized.csv"
)

FEDERAL_PATH = Path(
    "data/processed/v2/"
    "corporations_canada_normalized.csv"
)

OUTPUT_DIR = Path(
    "data/processed/v2/entity_resolution"
)

ENTITY_OUTPUT = OUTPUT_DIR / "toronto_local_entities.csv"
MEMBER_OUTPUT = OUTPUT_DIR / "toronto_entity_members.csv"
MATCH_OUTPUT = OUTPUT_DIR / "toronto_federal_matches.csv"


def clean(series):
    return (
        series.astype("string")
        .str.strip()
        .replace("", pd.NA)
    )


def normalize_name(series):
    return (
        clean(series)
        .str.upper()
        .str.replace(
            r"[^A-Z0-9]+",
            " ",
            regex=True,
        )
        .str.replace(
            r"\s+",
            " ",
            regex=True,
        )
        .str.strip()
        .replace("", pd.NA)
    )


def normalize_postal(series):
    return (
        clean(series)
        .str.upper()
        .str.replace(
            r"\s+",
            "",
            regex=True,
        )
    )


def normalize_address(series):
    return (
        clean(series)
        .str.upper()
        .str.replace(
            r"[^A-Z0-9]+",
            " ",
            regex=True,
        )
        .str.replace(
            r"\s+",
            " ",
            regex=True,
        )
        .str.strip()
        .replace("", pd.NA)
    )


def entity_hash(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:32]


def first_non_null(series):
    values = series.dropna()

    if values.empty:
        return pd.NA

    return values.iloc[0]


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Reading Toronto normalized data...")

    toronto = pd.read_csv(
        TORONTO_PATH,
        dtype="string",
        low_memory=False,
    )

    print(
        f"Toronto licences: {len(toronto):,}"
    )

    # -----------------------------------------
    # Federal comparison
    # -----------------------------------------

    print("Reading Federal normalized data...")

    federal = pd.read_csv(
        FEDERAL_PATH,
        dtype="string",
        low_memory=False,
    )

    federal["match_name"] = normalize_name(
        federal["legal_name"]
    )

    federal["match_postal"] = normalize_postal(
        federal["postal_code"]
    )

    federal["match_city"] = (
        clean(federal["city"])
        .str.upper()
    )

    federal["match_address"] = normalize_address(
        federal["street"]
    )

    # Unique authoritative candidate maps only.
    federal_name_counts = (
        federal["match_name"]
        .value_counts()
    )

    unique_federal_names = set(
        federal_name_counts[
            federal_name_counts.eq(1)
        ].index
    )

    federal_unique = federal[
        federal["match_name"].isin(
            unique_federal_names
        )
    ].copy()

    federal_lookup = (
        federal_unique
        .drop_duplicates("match_name")
        .set_index("match_name")
    )

    # -----------------------------------------
    # Toronto matching
    # -----------------------------------------

    toronto["match_name"] = (
        toronto["normalized_legal_name"]
        .fillna(
            toronto["normalized_display_name"]
        )
    )

    toronto["match_postal"] = normalize_postal(
        toronto["postal_code"]
    )

    toronto["match_city"] = (
        clean(toronto["city"])
        .str.upper()
    )

    toronto["match_address"] = normalize_address(
        toronto["street"]
    )

    toronto["federal_match_category"] = (
        "NO_FEDERAL_UNIQUE_NAME_MATCH"
    )

    toronto["matched_federal_number"] = pd.NA

    for idx, row in toronto.iterrows():

        name = row["match_name"]

        if pd.isna(name):
            continue

        if name not in federal_lookup.index:
            continue

        fed = federal_lookup.loc[name]

        same_postal = (
            pd.notna(row["match_postal"])
            and pd.notna(fed["match_postal"])
            and row["match_postal"]
            == fed["match_postal"]
        )

        same_city = (
            pd.notna(row["match_city"])
            and pd.notna(fed["match_city"])
            and row["match_city"]
            == fed["match_city"]
        )

        same_address = (
            pd.notna(row["match_address"])
            and pd.notna(fed["match_address"])
            and row["match_address"]
            == fed["match_address"]
        )

        if same_postal and same_address:
            category = (
                "FEDERAL_NAME_POSTAL_ADDRESS"
            )

        elif same_postal and same_city:
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

        toronto.at[
            idx,
            "federal_match_category",
        ] = category

        toronto.at[
            idx,
            "matched_federal_number",
        ] = fed["federal_corporation_number"]

    strong_categories = {
        "FEDERAL_NAME_POSTAL_ADDRESS",
        "FEDERAL_NAME_POSTAL_CITY",
        "FEDERAL_NAME_POSTAL",
    }

    toronto["strong_federal_match"] = (
        toronto[
            "federal_match_category"
        ].isin(strong_categories)
    )

    # -----------------------------------------
    # Local Toronto entity identity
    # -----------------------------------------

    local = toronto[
        ~toronto["strong_federal_match"]
    ].copy()

    def build_identity(row):

        name = row["normalized_display_name"]

        if pd.isna(name):
            name = row["normalized_legal_name"]

        if pd.isna(name):
            return (
                "LICENCE|"
                + str(row["source_record_id"]),
                "LICENCE_FALLBACK",
                50,
            )

        postal = row["match_postal"]
        address = row["match_address"]
        city = row["match_city"]

        if (
            pd.notna(postal)
            and pd.notna(address)
        ):
            return (
                f"{name}|{postal}|{address}",
                "NAME_POSTAL_ADDRESS",
                95,
            )

        if (
            pd.notna(city)
            and pd.notna(address)
        ):
            return (
                f"{name}|{city}|{address}",
                "NAME_CITY_ADDRESS",
                90,
            )

        if pd.notna(postal):
            return (
                f"{name}|{postal}",
                "NAME_POSTAL",
                85,
            )

        if pd.notna(city):
            return (
                f"{name}|{city}",
                "NAME_CITY",
                70,
            )

        return (
            "LICENCE|"
            + str(row["source_record_id"]),
            "LICENCE_FALLBACK",
            50,
        )

    identity_values = local.apply(
        build_identity,
        axis=1,
        result_type="expand",
    )

    identity_values.columns = [
        "identity_key",
        "identity_method",
        "identity_confidence_score",
    ]

    local[
        [
            "identity_key",
            "identity_method",
            "identity_confidence_score",
        ]
    ] = identity_values

    local["local_entity_key"] = (
        local["identity_key"]
        .map(entity_hash)
    )

    # -----------------------------------------
    # Canonical entities
    # -----------------------------------------

    grouped = local.groupby(
        "local_entity_key",
        dropna=False,
    )

    entities = grouped.agg(
        legal_name=(
            "legal_name",
            first_non_null,
        ),
        operating_name=(
            "operating_name",
            first_non_null,
        ),
        display_name=(
            "display_name",
            first_non_null,
        ),
        street=(
            "street",
            first_non_null,
        ),
        city=(
            "city",
            first_non_null,
        ),
        province=(
            "province",
            first_non_null,
        ),
        country=(
            "country",
            first_non_null,
        ),
        postal_code=(
            "postal_code",
            first_non_null,
        ),
        phone=(
            "phone",
            first_non_null,
        ),
        phone_extension=(
            "phone_extension",
            first_non_null,
        ),
        industry=(
            "industry",
            first_non_null,
        ),
        endorsements=(
            "endorsements",
            first_non_null,
        ),
        first_issued_at=(
            "issued_at",
            "min",
        ),
        latest_source_update_at=(
            "source_updated_at",
            "max",
        ),
        identity_method=(
            "identity_method",
            first_non_null,
        ),
        identity_confidence_score=(
            "identity_confidence_score",
            "max",
        ),
        source_record_count=(
            "source_record_id",
            "count",
        ),
    ).reset_index()

    # Quality score: deterministic completeness,
    # not a probability.
    entities["quality_score"] = (
        entities["legal_name"]
        .notna().astype(int) * 20
        + entities["street"]
        .notna().astype(int) * 15
        + entities["city"]
        .notna().astype(int) * 10
        + entities["postal_code"]
        .notna().astype(int) * 15
        + entities["industry"]
        .notna().astype(int) * 15
        + entities["phone"]
        .notna().astype(int) * 25
    )

    entities["identity_quality"] = (
        "REVIEW_REQUIRED"
    )

    entities.loc[
        entities[
            "identity_confidence_score"
        ].astype(float) >= 90,
        "identity_quality",
    ] = "HIGH_CONFIDENCE"

    entities.loc[
        entities[
            "identity_confidence_score"
        ].astype(float).between(
            70,
            89,
        ),
        "identity_quality",
    ] = "MEDIUM_CONFIDENCE"

    # New flags at canonical entity level.
    reference_time = pd.to_datetime(
        toronto["reference_time"].iloc[0],
        utc=True,
    )

    first_issued = pd.to_datetime(
        entities["first_issued_at"],
        errors="coerce",
        utc=True,
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

    # -----------------------------------------
    # Save reports
    # -----------------------------------------

    toronto.to_csv(
        MATCH_OUTPUT,
        index=False,
    )

    entities.to_csv(
        ENTITY_OUTPUT,
        index=False,
    )

    local.to_csv(
        MEMBER_OUTPUT,
        index=False,
    )

    print(
        "\n=== TORONTO ENTITY RESOLUTION ==="
    )

    print(
        f"Current licence records: "
        f"{len(toronto):,}"
    )

    print(
        f"Strong federal matches: "
        f"{toronto['strong_federal_match'].sum():,}"
    )

    print(
        f"Local candidate licence records: "
        f"{len(local):,}"
    )

    print(
        f"Canonical Toronto entities: "
        f"{len(entities):,}"
    )

    print("\nFederal match categories:")
    print(
        toronto[
            "federal_match_category"
        ]
        .value_counts()
        .to_string()
    )

    print("\nIdentity quality:")
    print(
        entities[
            "identity_quality"
        ]
        .value_counts()
        .to_string()
    )

    print(
        "\nEntities with phone: "
        f"{entities['phone'].notna().sum():,}"
    )

    print(
        "New 7 days: "
        f"{entities['is_new_7d'].sum():,}"
    )

    print(
        "New 30 days: "
        f"{entities['is_new_30d'].sum():,}"
    )

    print(
        f"\nEntities: {ENTITY_OUTPUT}"
    )
    print(
        f"Members: {MEMBER_OUTPUT}"
    )
    print(
        f"Match report: {MATCH_OUTPUT}"
    )

    print(
        "\nNo database records were modified."
    )


if __name__ == "__main__":
    main()