from pathlib import Path
import re

import pandas as pd


INPUT = Path(
    "data/raw/v2/toronto_business_licences.csv"
)

OUTPUT = Path(
    "data/processed/v2/"
    "toronto_business_licences_normalized.csv"
)


def clean_text(series):
    return (
        series.astype("string")
        .str.strip()
        .replace(
            {
                "": pd.NA,
                "nan": pd.NA,
                "None": pd.NA,
            }
        )
    )


def normalize_name(series):
    s = clean_text(series).str.upper()

    s = s.str.replace(
        r"[^A-Z0-9]+",
        " ",
        regex=True,
    )

    return (
        s.str.replace(
            r"\s+",
            " ",
            regex=True,
        )
        .str.strip()
        .replace("", pd.NA)
    )


def normalize_phone(series):
    s = clean_text(series)

    digits = s.str.replace(
        r"\D",
        "",
        regex=True,
    )

    # Canadian/US numbers sometimes include +1.
    digits = digits.str.replace(
        r"^1(?=\d{10}$)",
        "",
        regex=True,
    )

    valid = digits.str.len().eq(10)

    return digits.where(valid, pd.NA)


def parse_city_province(series):
    """
    Examples:
        TORONTO, ON
        MISSISSAUGA, ON
    """
    s = clean_text(series)

    split = s.str.rsplit(
        ",",
        n=1,
        expand=True,
    )

    city = clean_text(split[0])

    if split.shape[1] > 1:
        province = clean_text(split[1])
    else:
        province = pd.Series(
            pd.NA,
            index=s.index,
            dtype="string",
        )

    return city, province


def main():
    print("Reading Toronto business licences...")

    df = pd.read_csv(
        INPUT,
        dtype="string",
        low_memory=False,
    )

    raw_rows = len(df)

    # -----------------------------------------
    # Clean important fields
    # -----------------------------------------

    for col in [
        "Licence No.",
        "Operating Name",
        "Client Name",
        "Business Phone",
        "Business Phone Ext.",
        "Licence Address Line 1",
        "Licence Address Line 2",
        "Licence Address Line 3",
        "Category",
        "Endorsements",
        "Cancel Date",
        "Last Record Update",
    ]:
        df[col] = clean_text(df[col])

    df["issued_at"] = pd.to_datetime(
        df["Issued"],
        errors="coerce",
        utc=True,
    )

    df["cancelled_at"] = pd.to_datetime(
        df["Cancel Date"],
        errors="coerce",
        utc=True,
    )

    df["source_updated_at"] = pd.to_datetime(
        df["Last Record Update"],
        errors="coerce",
        utc=True,
    )

    # -----------------------------------------
    # Current usable licences
    # -----------------------------------------

    current = df[
        df["Licence No."].notna()
        & df["Client Name"].notna()
        & df["cancelled_at"].isna()
    ].copy()

    # Prevent duplicate source records.
    current = current.drop_duplicates(
        subset=["Licence No."],
        keep="last",
    )

    # -----------------------------------------
    # Business identity
    # -----------------------------------------

    current["legal_name"] = current[
        "Client Name"
    ]

    current["operating_name"] = current[
        "Operating Name"
    ]

    current["display_name"] = (
        current["operating_name"]
        .fillna(current["legal_name"])
    )

    current["normalized_legal_name"] = (
        normalize_name(
            current["legal_name"]
        )
    )

    current["normalized_operating_name"] = (
        normalize_name(
            current["operating_name"]
        )
    )

    current["normalized_display_name"] = (
        normalize_name(
            current["display_name"]
        )
    )

    # -----------------------------------------
    # Address
    # -----------------------------------------

    current["street"] = current[
        "Licence Address Line 1"
    ]

    (
        current["city"],
        current["province"],
    ) = parse_city_province(
        current["Licence Address Line 2"]
    )

    current["postal_code"] = (
        current["Licence Address Line 3"]
        .str.upper()
        .str.replace(
            r"\s+",
            "",
            regex=True,
        )
    )

    current["country"] = "CA"

    # -----------------------------------------
    # Phone
    # -----------------------------------------

    current["phone"] = normalize_phone(
        current["Business Phone"]
    )

    current["phone_extension"] = (
        current["Business Phone Ext."]
    )

    # -----------------------------------------
    # Industry
    # -----------------------------------------

    current["industry"] = current[
        "Category"
    ]

    current["endorsements"] = current[
        "Endorsements"
    ]

    # -----------------------------------------
    # New-business signals
    # -----------------------------------------

    reference_time = current[
        "source_updated_at"
    ].max()

    if pd.isna(reference_time):
        raise RuntimeError(
            "Unable to determine Toronto "
            "dataset reference time."
        )

    age_days = (
        reference_time
        - current["issued_at"]
    ).dt.total_seconds() / 86400

    current["is_new_1d"] = (
        current["issued_at"].notna()
        & age_days.ge(0)
        & age_days.le(1)
    )

    current["is_new_7d"] = (
        current["issued_at"].notna()
        & age_days.ge(0)
        & age_days.le(7)
    )

    current["is_new_30d"] = (
        current["issued_at"].notna()
        & age_days.ge(0)
        & age_days.le(30)
    )

    # -----------------------------------------
    # Source metadata
    # -----------------------------------------

    current["source_key"] = (
        "toronto_business_licences"
    )

    current["source_record_id"] = current[
        "Licence No."
    ]

    current["source_status"] = "Active"

    current["reference_time"] = (
        reference_time.isoformat()
    )

    # -----------------------------------------
    # Final output
    # -----------------------------------------

    columns = [
        "source_record_id",
        "legal_name",
        "operating_name",
        "display_name",
        "normalized_legal_name",
        "normalized_operating_name",
        "normalized_display_name",
        "street",
        "city",
        "province",
        "country",
        "postal_code",
        "phone",
        "phone_extension",
        "industry",
        "endorsements",
        "issued_at",
        "source_updated_at",
        "is_new_1d",
        "is_new_7d",
        "is_new_30d",
        "source_key",
        "source_status",
        "reference_time",
    ]

    result = current[columns].copy()

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT,
        index=False,
    )

    print(
        "\n=== TORONTO NORMALIZATION ==="
    )
    print(f"Raw rows: {raw_rows:,}")
    print(
        f"Current unique licences: "
        f"{len(result):,}"
    )
    print(
        f"Unique display names: "
        f"{result['normalized_display_name'].nunique():,}"
    )
    print(
        f"With phone: "
        f"{result['phone'].notna().sum():,}"
    )
    print(
        f"With street address: "
        f"{result['street'].notna().sum():,}"
    )
    print(
        f"New 1 day: "
        f"{result['is_new_1d'].sum():,}"
    )
    print(
        f"New 7 days: "
        f"{result['is_new_7d'].sum():,}"
    )
    print(
        f"New 30 days: "
        f"{result['is_new_30d'].sum():,}"
    )
    print(
        f"Reference time: {reference_time}"
    )
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()