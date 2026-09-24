from pathlib import Path

import pandas as pd


CORP_PATH = Path(
    "data/processed/corporations_canada_deduplicated.csv"
)

ODBUS_PATH = Path(
    "data/processed/statcan_odbus_normalized.csv"
)

OUTPUT_PATH = Path(
    "data/processed/corporations_canada_enriched.csv"
)


def normalize_name(series: pd.Series) -> pd.Series:
    """Create conservative normalized business-name matching keys."""
    return (
        series.astype("string")
        .str.upper()
        .str.strip()
        .str.replace(r"[^A-Z0-9]+", " ", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


def enrich_dataset() -> None:
    print("Loading Corporations Canada dataset...")
    corp = pd.read_csv(CORP_PATH, dtype=str, low_memory=False)

    print("Loading Statistics Canada ODBus...")
    odbus = pd.read_csv(ODBUS_PATH, dtype=str, low_memory=False)

    corp["business_name_match"] = normalize_name(corp["business_name"])
    corp["province"] = corp["province"].astype("string").str.upper().str.strip()

    odbus["business_name_match"] = (
        odbus["business_name_match"].astype("string").str.strip()
    )
    odbus["province"] = odbus["province"].astype("string").str.upper().str.strip()

    # Only automatically use ODBus keys that identify exactly one record.
    key_columns = ["business_name_match", "province"]

    valid_odbus = odbus.dropna(subset=key_columns).copy()

    key_counts = (
        valid_odbus.groupby(key_columns, dropna=False)
        .size()
        .reset_index(name="match_count")
    )

    unique_keys = key_counts[
        key_counts["match_count"] == 1
    ][key_columns]

    unique_odbus = valid_odbus.merge(
        unique_keys,
        on=key_columns,
        how="inner",
    )

    enrichment_columns = [
        "business_name_match",
        "province",
        "business_sector",
        "business_subsector",
        "business_description",
        "derived_NAICS",
        "source_NAICS_primary",
        "NAICS_descr",
        "latitude",
        "longitude",
        "total_no_employees",
        "provider",
        "source_record_id",
    ]

    unique_odbus = unique_odbus[enrichment_columns].rename(
        columns={
            "business_sector": "odbus_business_sector",
            "business_subsector": "odbus_business_subsector",
            "business_description": "odbus_business_description",
            "derived_NAICS": "odbus_derived_naics",
            "source_NAICS_primary": "odbus_source_naics_primary",
            "NAICS_descr": "odbus_naics_description",
            "latitude": "odbus_latitude",
            "longitude": "odbus_longitude",
            "total_no_employees": "odbus_total_employees",
            "provider": "odbus_provider",
            "source_record_id": "odbus_source_record_id",
        }
    )

    print("Matching unique business-name + province keys...")

    enriched = corp.merge(
        unique_odbus,
        on=["business_name_match", "province"],
        how="left",
        validate="many_to_one",
    )

    enriched["odbus_matched"] = (
        enriched["odbus_source_record_id"].notna()
    )

    matched_count = int(enriched["odbus_matched"].sum())

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(OUTPUT_PATH, index=False)

    print(f"Corporations Canada rows: {len(corp):,}")
    print(f"Unique ODBus matching records: {len(unique_odbus):,}")
    print(f"Successfully enriched rows: {matched_count:,}")
    print(
        f"Match rate: {(matched_count / len(corp)) * 100:.2f}%"
    )
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    enrich_dataset()