import csv
import io
import zipfile
from collections import Counter


ZIP_PATH = (
    r"C:\Users\Hp\Desktop\Project Video Editing"
    r"\Material\JeuDonnees.zip"
)


def main() -> None:
    print("=== QUEBEC REQ DOMAIN INSPECTION ===")
    print()

    with zipfile.ZipFile(ZIP_PATH, "r") as archive:

        # --------------------------------------------------
        # Read DomaineValeur lookup table
        # --------------------------------------------------

        with archive.open("DomaineValeur.csv") as raw:
            text = io.TextIOWrapper(
                raw,
                encoding="utf-8-sig",
                errors="replace",
                newline="",
            )

            reader = csv.DictReader(text)
            domain_rows = list(reader)

        print(
            f"DomaineValeur rows: {len(domain_rows):,}"
        )

        domain_types = Counter(
            row["TYP_DOM_VAL"]
            for row in domain_rows
        )

        print()
        print("=== AVAILABLE DOMAIN TYPES ===")

        for domain_type, count in sorted(
            domain_types.items()
        ):
            print(
                f"{domain_type}: {count:,}"
            )

        # --------------------------------------------------
        # Read actual codes used in Entreprise.csv
        # --------------------------------------------------

        target_columns = [
            "COD_INTVAL_EMPLO_QUE",
            "COD_STAT_IMMAT",
            "COD_FORME_JURI",
            "COD_REGIM_JURI",
            "COD_REGIM_JURI_CONSTI",
            "COD_ACT_ECON_CAE",
            "COD_ACT_ECON_CAE2",
        ]

        counters = {
            column: Counter()
            for column in target_columns
        }

        total = 0

        with archive.open("Entreprise.csv") as raw:
            text = io.TextIOWrapper(
                raw,
                encoding="utf-8-sig",
                errors="replace",
                newline="",
            )

            reader = csv.DictReader(text)

            for row in reader:
                total += 1

                for column in target_columns:
                    value = (
                        row.get(column) or ""
                    ).strip()

                    if value:
                        counters[column][value] += 1

        print()
        print(
            f"Entreprise records scanned: {total:,}"
        )

        # --------------------------------------------------
        # Display actual values and attempt exact lookup
        # --------------------------------------------------

        for column in target_columns:

            print()
            print("=" * 80)
            print(column)
            print("=" * 80)

            used_values = counters[column]

            print(
                f"Distinct nonblank codes: "
                f"{len(used_values):,}"
            )

            for code, count in used_values.most_common(30):

                matches = [
                    row
                    for row in domain_rows
                    if (
                        row["COD_DOM_VAL"].strip()
                        == code
                    )
                ]

                descriptions = sorted(
                    {
                        row["VAL_DOM_FRAN"].strip()
                        for row in matches
                        if row["VAL_DOM_FRAN"].strip()
                    }
                )

                description = (
                    " | ".join(descriptions)
                    if descriptions
                    else "NO EXACT DOMAIN MATCH"
                )

                print(
                    f"{code!r}: "
                    f"{count:,} records -> "
                    f"{description}"
                )

    print()
    print(
        "=== QUEBEC REQ DOMAIN INSPECTION COMPLETE ==="
    )


if __name__ == "__main__":
    main()