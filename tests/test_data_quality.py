from pathlib import Path

import pandas as pd


DATA_PATH = Path(
    "data/processed/corporations_canada_enriched.csv"
)


def load_data():
    assert DATA_PATH.exists(), (
        f"Processed dataset not found: {DATA_PATH}"
    )

    return pd.read_csv(
        DATA_PATH,
        dtype=str,
        low_memory=False,
    )


def test_dataset_not_empty():
    df = load_data()
    assert len(df) > 0


def test_required_columns_exist():
    df = load_data()

    required_columns = {
        "corporation_number",
        "business_name",
        "province",
        "status",
        "source",
        "source_record_id",
        "odbus_matched",
    }

    missing = required_columns - set(df.columns)

    assert not missing, (
        f"Missing required columns: {sorted(missing)}"
    )


def test_corporation_number_not_null():
    df = load_data()
    assert df["corporation_number"].notna().all()


def test_corporation_number_unique():
    df = load_data()

    duplicates = df["corporation_number"].duplicated().sum()

    assert duplicates == 0, (
        f"Found {duplicates} duplicate corporation numbers"
    )


def test_business_name_not_null():
    df = load_data()

    missing_names = df["business_name"].isna().sum()

    assert missing_names == 0, (
        f"Found {missing_names} records without business names"
    )


def test_source_present():
    df = load_data()
    assert df["source"].notna().all()