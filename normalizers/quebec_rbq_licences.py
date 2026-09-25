from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw/v2")
PROCESSED_DIR = Path("data/processed/v2")

INPUT_FILE = (
    RAW_DIR
    / "quebec_rbq_active_licences"
    / "rdl01_ExtractionDonneesOuvertes.csv"
)

METADATA_FILE = (
    RAW_DIR
    / "quebec_rbq_active_licences_metadata.json"
)

OUTPUT_FILE = (
    PROCESSED_DIR
    / "quebec_rbq_licences_normalized.csv"
)

SUMMARY_FILE = (
    PROCESSED_DIR
    / "quebec_rbq_licences_summary.json"
)


def clean_text(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if not value:
        return None

    return re.sub(r"\s+", " ", value)


def normalize_name(value):
    value = clean_text(value)

    if not value:
        return None

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = value.upper()

    value = re.sub(
        r"[^A-Z0-9]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def clean_neq(value):
    value = clean_text(value)

    if not value:
        return None

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    # Québec NEQ normally contains 10 digits.
    if len(digits) != 10:
        return None

    return digits


def clean_phone(value):
    value = clean_text(value)

    if not value:
        return None

    digits = re.sub(
        r"\D",
        "",
        value,
    )

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        return value

    return (
        f"{digits[0:3]}-"
        f"{digits[3:6]}-"
        f"{digits[6:10]}"
    )


def clean_email(value):
    value = clean_text(value)

    if not value:
        return None

    value = value.lower()

    if "@" not in value:
        return None

    return value


def parse_date(series):
    return pd.to_datetime(
        series,
        errors="coerce",
    ).dt.date


def main():
    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "Reading Québec RBQ active licences..."
    )

    df = pd.read_csv(
        INPUT_FILE,
        dtype=str,
        encoding="utf-8-sig",
        low_memory=False,
    )

    raw_rows = len(df)

    print(
        f"Raw licence rows: {raw_rows:,}"
    )

    metadata = json.loads(
        METADATA_FILE.read_text(
            encoding="utf-8"
        )
    )

    collected_at = metadata[
        "collected_at_utc"
    ]

    source_updated_at = metadata.get(
        "last_modified"
    )

    # Rename official French fields into
    # internal English field names.
    df = df.rename(
        columns={
            "Numéro de licence":
                "licence_number",

            "Statut de la licence":
                "licence_status",

            "Type de licence":
                "licence_type",

            "Date de délivrance":
                "issue_date",

            "Restriction":
                "restriction",

            "Date de début de la restriction":
                "restriction_start_date",

            "Date de fin de la restriction":
                "restriction_end_date",

            "Association ou compagnie fournissant le cautionnement":
                "bond_provider",

            "Montant de la caution":
                "bond_amount",

            "Date du paiement annuel":
                "annual_payment_date",

            "Mandataire":
                "representative",

            "Courriel":
                "email",

            "Adresse":
                "address",

            "NEQ":
                "neq",

            "Nom de l'intervenant":
                "legal_name",

            "Numéro de téléphone":
                "phone",

            "Municipalité":
                "city",

            "Statut juridique":
                "legal_status",

            "Code de région administrative":
                "administrative_region_code",

            "Région administrative":
                "administrative_region",

            "Nombre de sous-catégorie autorisées":
                "authorized_subcategory_count",

            "Categorie":
                "category",

            "Sous-catégories":
                "subcategories",

            "Autre nom":
                "operating_name",
        }
    )

    required_columns = [
        "licence_number",
        "licence_status",
        "neq",
        "legal_name",
    ]

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise RuntimeError(
            "Missing expected RBQ columns: "
            + ", ".join(missing)
        )

    text_columns = [
        "licence_number",
        "licence_status",
        "licence_type",
        "restriction",
        "bond_provider",
        "bond_amount",
        "representative",
        "address",
        "legal_name",
        "city",
        "legal_status",
        "administrative_region_code",
        "administrative_region",
        "authorized_subcategory_count",
        "category",
        "subcategories",
        "operating_name",
    ]

    for column in text_columns:
        if column in df.columns:
            df[column] = df[column].map(
                clean_text
            )

    df["neq"] = df["neq"].map(
        clean_neq
    )

    df["email"] = df["email"].map(
        clean_email
    )

    df["phone"] = df["phone"].map(
        clean_phone
    )

    df["normalized_legal_name"] = (
        df["legal_name"].map(
            normalize_name
        )
    )

    df["normalized_operating_name"] = (
        df["operating_name"].map(
            normalize_name
        )
    )

    df["normalized_city"] = (
        df["city"].map(
            normalize_name
        )
    )

    df["issue_date"] = parse_date(
        df["issue_date"]
    )

    df["restriction_start_date"] = (
        parse_date(
            df["restriction_start_date"]
        )
    )

    df["restriction_end_date"] = (
        parse_date(
            df["restriction_end_date"]
        )
    )

    df["annual_payment_date"] = (
        parse_date(
            df["annual_payment_date"]
        )
    )

    # A usable record must have a licence number
    # and at least a legal or operating name.
    usable = df[
        df["licence_number"].notna()
        & (
            df["legal_name"].notna()
            | df["operating_name"].notna()
        )
    ].copy()

    # Source-record identity is the licence number.
    # Keep one row per licence number.
    usable = (
        usable
        .sort_values(
            by=[
                "licence_number",
                "issue_date",
            ],
            na_position="first",
        )
        .drop_duplicates(
            subset=["licence_number"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    usable["source_key"] = (
        "quebec_rbq_active_licences"
    )

    usable["source_record_id"] = (
        usable["licence_number"]
    )

    usable["province"] = "QC"
    usable["country"] = "CA"

    usable["collected_at_utc"] = (
        collected_at
    )

    usable["source_updated_at"] = (
        source_updated_at
    )

    usable["source_sha256"] = (
        metadata["sha256"]
    )

    # Business-level analysis only.
    # Do NOT collapse licence records yet.
    valid_neq = usable[
        usable["neq"].notna()
    ]

    unique_neq = (
        valid_neq["neq"].nunique()
    )

    no_neq = (
        usable["neq"].isna().sum()
    )

    unique_legal_names = (
        usable[
            "normalized_legal_name"
        ]
        .dropna()
        .nunique()
    )

    with_email = (
        usable["email"]
        .notna()
        .sum()
    )

    with_phone = (
        usable["phone"]
        .notna()
        .sum()
    )

    with_address = (
        usable["address"]
        .notna()
        .sum()
    )

    status_counts = (
        usable["licence_status"]
        .fillna("NULL")
        .value_counts()
        .to_dict()
    )

    # How many licence records are attached
    # to each valid NEQ?
    neq_licence_counts = (
        valid_neq
        .groupby("neq")
        .size()
    )

    neq_multi_licence = int(
        (neq_licence_counts > 1).sum()
    )

    max_licences_per_neq = (
        int(neq_licence_counts.max())
        if not neq_licence_counts.empty
        else 0
    )

    output_columns = [
        "licence_number",
        "licence_status",
        "licence_type",
        "issue_date",
        "restriction",
        "restriction_start_date",
        "restriction_end_date",
        "bond_provider",
        "bond_amount",
        "annual_payment_date",
        "representative",
        "email",
        "address",
        "neq",
        "legal_name",
        "operating_name",
        "phone",
        "city",
        "province",
        "country",
        "legal_status",
        "administrative_region_code",
        "administrative_region",
        "authorized_subcategory_count",
        "category",
        "subcategories",
        "normalized_legal_name",
        "normalized_operating_name",
        "normalized_city",
        "source_key",
        "source_record_id",
        "collected_at_utc",
        "source_updated_at",
        "source_sha256",
    ]

    usable[
        output_columns
    ].to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8",
    )

    summary = {
        "raw_rows": raw_rows,
        "usable_unique_licence_records":
            len(usable),
        "records_with_valid_neq":
            int(len(valid_neq)),
        "unique_valid_neq":
            int(unique_neq),
        "records_without_valid_neq":
            int(no_neq),
        "unique_normalized_legal_names":
            int(unique_legal_names),
        "records_with_email":
            int(with_email),
        "records_with_phone":
            int(with_phone),
        "records_with_address":
            int(with_address),
        "neq_with_multiple_licences":
            neq_multi_licence,
        "max_licences_for_one_neq":
            max_licences_per_neq,
        "licence_status_counts":
            status_counts,
        "source_updated_at":
            source_updated_at,
        "collected_at_utc":
            collected_at,
    }

    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=== QUÉBEC RBQ NORMALIZATION ==="
    )

    print(
        f"Raw rows: {raw_rows:,}"
    )

    print(
        "Usable unique licence records: "
        f"{len(usable):,}"
    )

    print(
        "Records with valid NEQ: "
        f"{len(valid_neq):,}"
    )

    print(
        f"Unique valid NEQs: {unique_neq:,}"
    )

    print(
        "Records without valid NEQ: "
        f"{no_neq:,}"
    )

    print(
        "Unique normalized legal names: "
        f"{unique_legal_names:,}"
    )

    print(
        f"With email: {with_email:,}"
    )

    print(
        f"With phone: {with_phone:,}"
    )

    print(
        f"With address: {with_address:,}"
    )

    print(
        "NEQs with multiple licences: "
        f"{neq_multi_licence:,}"
    )

    print(
        "Maximum licences for one NEQ: "
        f"{max_licences_per_neq:,}"
    )

    print()
    print("Licence statuses:")

    for status, count in (
        sorted(
            status_counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ):
        print(
            f"  {status}: {count:,}"
        )

    print()
    print(
        f"Output: {OUTPUT_FILE}"
    )

    print(
        f"Summary: {SUMMARY_FILE}"
    )

    print()
    print(
        "Québec RBQ normalization completed."
    )


if __name__ == "__main__":
    main()