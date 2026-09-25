from pathlib import Path
import json
import re

import pandas as pd


RAW_FILE = Path(
    "data/raw/v2/edmonton_business_licences.json"
)

META_FILE = Path(
    "data/raw/v2/edmonton_business_licences_metadata.json"
)

OUT_FILE = Path(
    "data/processed/v2/"
    "edmonton_business_licences_normalized.csv"
)


def clean(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def normalize_name(value):
    value = clean(value)

    if value is None:
        return None

    return re.sub(
        r"[^A-Z0-9]+",
        "",
        value.upper(),
    )


def main():
    print("Reading Edmonton raw data...")

    rows = json.loads(
        RAW_FILE.read_text(encoding="utf-8")
    )

    metadata = json.loads(
        META_FILE.read_text(encoding="utf-8")
    )

    df = pd.DataFrame(rows)

    print(f"Raw records: {len(df):,}")

    # -----------------------------------
    # Basic required fields
    # -----------------------------------

    df["business_name"] = (
        df["business_name"]
        .astype("string")
        .str.strip()
    )

    df["source_record_id"] = (
        df["externalid"]
        .astype("string")
        .str.strip()
    )

    invalid_names = {
        "",
        "NONE",
        "NULL",
        "N/A",
        "NA",
        "<NA>",
        "REDACTED",
        "<REDACTED FOR PRIVACY>",
    }

    name_clean = (
        df["business_name"]
        .fillna("")
        .str.strip()
        .str.upper()
    )

    record_clean = (
        df["source_record_id"]
        .fillna("")
        .str.strip()
    )

    df = df[
        ~name_clean.isin(invalid_names)
        & record_clean.ne("")
    ].copy()

    # -----------------------------------
    # Dates
    # -----------------------------------

    df["most_recent_issue_date"] = pd.to_datetime(
        df.get("most_recent_issue_date"),
        errors="coerce",
        utc=True,
    )

    df["expiry_date"] = pd.to_datetime(
        df.get("expiry_date"),
        errors="coerce",
        utc=True,
    )

    df["original_issue_date"] = pd.to_datetime(
        df.get("originalissuedate"),
        errors="coerce",
        utc=True,
    )

    # Use collection time as the
    # reproducible freshness reference.
    reference_time = pd.Timestamp(
        metadata["collected_at_utc"]
    )

    if reference_time.tzinfo is None:
        reference_time = reference_time.tz_localize(
            "UTC"
        )

    # Current licence:
    # expiry date has not passed.
    current = df[
        df["expiry_date"].notna()
        & (df["expiry_date"] >= reference_time)
    ].copy()

    # One source record per licence ID.
    current = (
        current
        .sort_values(
            "most_recent_issue_date",
            na_position="first",
        )
        .drop_duplicates(
            subset=["source_record_id"],
            keep="last",
        )
    )

    # -----------------------------------
    # Address
    # -----------------------------------

    current["street"] = (
        current.get(
            "business_address",
            pd.Series(
                index=current.index,
                dtype="string",
            ),
        )
        .astype("string")
        .str.strip()
    )

    # Edmonton deliberately suppresses
    # home-based addresses.
    home_mask = (
        current["street"]
        .str.contains(
            "Home Based Business",
            case=False,
            na=False,
        )
    )

    current.loc[
        home_mask,
        "street",
    ] = pd.NA

    # -----------------------------------
    # Normalized output
    # -----------------------------------

    out = pd.DataFrame(
        {
            "source_key":
                "edmonton_business_licences",

            "source_record_id":
                current["source_record_id"],

            "legal_name":
                current["business_name"],

            "operating_name":
                current["business_name"],

            "normalized_legal_name":
                current["business_name"]
                .map(normalize_name),

            "street":
                current["street"],

            "city":
                "Edmonton",

            "province":
                "AB",

            "country":
                "CA",

            "postal_code":
                pd.NA,

            "industry":
                current.get(
                    "business_licence_category"
                ),

            "licence_type":
                current.get("licencetype"),

            "neighbourhood":
                current.get("neighbourhood"),

            "neighbourhood_id":
                current.get("neighbourhood_id"),

            "ward":
                current.get("ward"),

            "original_issue_date":
                current["original_issue_date"],

            "most_recent_issue_date":
                current["most_recent_issue_date"],

            "expiry_date":
                current["expiry_date"],

            "source_updated_at":
                current["most_recent_issue_date"],

            "collected_at_utc":
                metadata["collected_at_utc"],
        }
    )

    # -----------------------------------
    # New-business signals
    # -----------------------------------

    age = (
        reference_time
        - out["most_recent_issue_date"]
    ).dt.total_seconds() / 86400

    out["is_new_1d"] = (
        age.ge(0) & age.le(1)
    )

    out["is_new_7d"] = (
        age.ge(0) & age.le(7)
    )

    out["is_new_30d"] = (
        age.ge(0) & age.le(30)
    )

    OUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_csv(
        OUT_FILE,
        index=False,
    )

    print("\n=== EDMONTON NORMALIZATION ===")
    print(f"Raw records: {len(df):,}")
    print(
        f"Current unique licences: "
        f"{len(out):,}"
    )
    print(
        f"Unique normalized names: "
        f"{out['normalized_legal_name'].nunique():,}"
    )
    print(
        f"With visible street address: "
        f"{out['street'].notna().sum():,}"
    )
    print(
        f"New 1 day: "
        f"{out['is_new_1d'].sum():,}"
    )
    print(
        f"New 7 days: "
        f"{out['is_new_7d'].sum():,}"
    )
    print(
        f"New 30 days: "
        f"{out['is_new_30d'].sum():,}"
    )
    print(f"Reference time: {reference_time}")
    print(f"Output: {OUT_FILE}")


if __name__ == "__main__":
    main()