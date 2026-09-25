from pathlib import Path
import hashlib

import pandas as pd


VANCOUVER_PATH = Path(
    "data/processed/v2/vancouver_business_licences_normalized.csv"
)

MATCH_PATH = Path(
    "data/processed/v2/match_analysis/"
    "vancouver_federal_candidates.csv"
)

OUTPUT_DIR = Path(
    "data/processed/v2/entity_resolution"
)

ENTITY_OUTPUT = OUTPUT_DIR / "vancouver_local_entities.csv"
MEMBERS_OUTPUT = OUTPUT_DIR / "vancouver_entity_members.csv"


def clean(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.upper()
        .str.strip()
        .replace("", pd.NA)
    )


def make_hash(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:24]


def employee_bucket(number):
    if pd.isna(number):
        return pd.NA

    number = int(number)

    if number == 0:
        return "0"
    if number <= 4:
        return "1-4"
    if number <= 9:
        return "5-9"
    if number <= 19:
        return "10-19"
    if number <= 49:
        return "20-49"
    if number <= 99:
        return "50-99"
    if number <= 199:
        return "100-199"
    if number <= 499:
        return "200-499"
    if number <= 999:
        return "500-999"

    return "1,000+"


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Reading normalized Vancouver records...")

    van = pd.read_csv(
        VANCOUVER_PATH,
        dtype="string",
        low_memory=False,
    )

    van = van[
        van["is_current_usable"]
        .str.lower()
        .eq("true")
    ].copy()

    # Defensive licence-level deduplication.
    van = van.sort_values(
        ["source_record_id", "extract_at"],
        na_position="first",
    ).drop_duplicates(
        subset=["source_record_id"],
        keep="last",
    )

    print(
        f"Current unique licence records: {len(van):,}"
    )

    print("Reading federal match analysis...")

    matches = pd.read_csv(
        MATCH_PATH,
        dtype="string",
        low_memory=False,
        usecols=[
            "source_record_id",
            "match_category",
        ],
    )

    matches = matches.drop_duplicates(
        subset=["source_record_id"],
        keep="last",
    )

    van = van.merge(
        matches,
        on="source_record_id",
        how="left",
        validate="one_to_one",
    )

    if van["match_category"].isna().any():
        missing = int(
            van["match_category"].isna().sum()
        )
        raise RuntimeError(
            f"{missing:,} Vancouver records are "
            "missing match-analysis results."
        )

    # For this stage we build local entities only from
    # records having NO federal name match.
    #
    # Review categories remain outside automatic insertion.
    local = van[
        van["match_category"].eq(
            "NO_FEDERAL_NAME_MATCH"
        )
    ].copy()

    print(
        "No-federal-name-match licence records: "
        f"{len(local):,}"
    )

    local["name_key"] = clean(
        local["normalized_business_name"]
    )

    local["postal_key"] = (
        clean(local["postal_code"])
        .str.replace(
            " ",
            "",
            regex=False,
        )
    )

    local["address_key"] = clean(
        local["street_address"]
    )

    local["city_key"] = clean(
        local["city"]
    )

    if local["name_key"].isna().any():
        raise RuntimeError(
            "Local candidate without normalized "
            "business name detected."
        )

    # -------------------------------------------------
    # Conservative local identity hierarchy
    # -------------------------------------------------
    #
    # 1. Name + postal + address
    # 2. Name + postal
    # 3. Name + city + address
    # 4. Name + city
    # 5. Name + licence record ID as final fallback
    #
    # The fallback intentionally avoids merging
    # insufficiently identified businesses.

    def identity_key(row):
        name = row["name_key"]
        postal = row["postal_key"]
        address = row["address_key"]
        city = row["city_key"]

        if pd.notna(postal) and pd.notna(address):
            return (
                f"NAME_POSTAL_ADDRESS|"
                f"{name}|{postal}|{address}"
            )

        if pd.notna(postal):
            return (
                f"NAME_POSTAL|"
                f"{name}|{postal}"
            )

        if pd.notna(city) and pd.notna(address):
            return (
                f"NAME_CITY_ADDRESS|"
                f"{name}|{city}|{address}"
            )

        if pd.notna(city):
            return (
                f"NAME_CITY|"
                f"{name}|{city}"
            )

        return (
            f"LICENCE_FALLBACK|"
            f"{name}|{row['source_record_id']}"
        )

    local["identity_key"] = local.apply(
        identity_key,
        axis=1,
    )

    local["local_entity_key"] = (
        local["identity_key"].map(make_hash)
    )

    # Parse numeric employee count.
    local["employee_count_numeric"] = (
        pd.to_numeric(
            local["employee_count"],
            errors="coerce",
        ).astype("Int64")
    )

    # Aggregate source licences into canonical
    # local operating entities.
    #
    # max employee count is retained conservatively
    # for repeated licences representing the same
    # location/entity. Source rows remain available
    # separately in MEMBERS_OUTPUT.

    grouped = local.groupby(
        "local_entity_key",
        dropna=False,
        sort=False,
    )

    entities = grouped.agg(
        legal_name=(
            "BusinessName",
            "first",
        ),
        operating_name=(
            "BusinessTradeName",
            "first",
        ),
        display_name=(
            "display_name",
            "first",
        ),
        normalized_business_name=(
            "name_key",
            "first",
        ),
        street=(
            "street_address",
            "first",
        ),
        city=(
            "city",
            "first",
        ),
        province=(
            "province",
            "first",
        ),
        country=(
            "country",
            "first",
        ),
        postal_code=(
            "postal_code",
            "first",
        ),
        business_type=(
            "BusinessType",
            "first",
        ),
        business_subtype=(
            "BusinessSubType",
            "first",
        ),
        local_area=(
            "LocalArea",
            "first",
        ),
        employee_count=(
            "employee_count_numeric",
            "max",
        ),
        source_record_count=(
            "source_record_id",
            "nunique",
        ),
        first_issued_at=(
            "issued_at",
            "min",
        ),
        latest_extract_at=(
            "extract_at",
            "max",
        ),
        identity_method=(
            "identity_key",
            lambda x: x.iloc[0].split("|", 1)[0],
        ),
    ).reset_index()

    entities["employee_size_bucket"] = (
        entities["employee_count"].map(
            employee_bucket
        )
    )

    # Every local source record maps to exactly
    # one local entity.
    members = local[
        [
            "local_entity_key",
            "source_record_id",
            "LicenceNumber",
            "LicenceRevisionNumber",
            "FOLDERYEAR",
            "display_name",
            "BusinessType",
            "BusinessSubType",
            "employee_count",
            "issued_at",
            "expired_at",
            "extract_at",
        ]
    ].copy()

    if members["source_record_id"].duplicated().any():
        raise RuntimeError(
            "A source licence was assigned more "
            "than once."
        )

    if entities["local_entity_key"].duplicated().any():
        raise RuntimeError(
            "Duplicate canonical local entity "
            "keys detected."
        )

    if len(members) != len(local):
        raise RuntimeError(
            "Entity-member reconciliation failed."
        )

    entities.to_csv(
        ENTITY_OUTPUT,
        index=False,
    )

    members.to_csv(
        MEMBERS_OUTPUT,
        index=False,
    )

    print(
        "\n=== VANCOUVER LOCAL ENTITY BUILD ==="
    )

    print(
        "Candidate licence records: "
        f"{len(local):,}"
    )

    print(
        "Canonical local entities: "
        f"{len(entities):,}"
    )

    print(
        "Licence rows collapsed: "
        f"{len(local) - len(entities):,}"
    )

    print(
        "\nIdentity methods:"
    )

    print(
        entities["identity_method"]
        .value_counts()
        .to_string()
    )

    print(
        "\nEmployee-size buckets:"
    )

    print(
        entities["employee_size_bucket"]
        .fillna("<NULL>")
        .value_counts()
        .to_string()
    )

    print(
        "\nEntities with multiple licence records: "
        f"{int((entities['source_record_count'] > 1).sum()):,}"
    )

    print(
        "\nNo database records were modified."
    )

    print(
        f"\nEntities: {ENTITY_OUTPUT}"
    )

    print(
        f"Members: {MEMBERS_OUTPUT}"
    )


if __name__ == "__main__":
    main()