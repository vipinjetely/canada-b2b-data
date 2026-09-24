from pathlib import Path

import pandas as pd


INPUT_PATH = Path("data/processed/corporations_canada_normalized.csv")
OUTPUT_PATH = Path("data/processed/corporations_canada_deduplicated.csv")


def deduplicate_dataset() -> None:
    """Deduplicate Corporations Canada records using corporation number."""

    print("Reading normalized dataset...")

    df = pd.read_csv(INPUT_PATH, dtype=str, low_memory=False)

    original_count = len(df)

    missing_id_count = df["corporation_number"].isna().sum()

    if missing_id_count:
        raise ValueError(
            f"Found {missing_id_count:,} records without corporation_number."
        )

    duplicate_count = df.duplicated(
        subset=["corporation_number"],
        keep="first",
    ).sum()

    df = df.drop_duplicates(
        subset=["corporation_number"],
        keep="first",
    ).copy()

    final_count = len(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Input rows: {original_count:,}")
    print(f"Duplicate corporation IDs removed: {duplicate_count:,}")
    print(f"Output rows: {final_count:,}")
    print(f"Saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    deduplicate_dataset()