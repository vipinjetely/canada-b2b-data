from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

BASE_DIR = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "enrichment"
)

RESEARCH_FILE = BASE_DIR / "decision_maker_research.csv"


COLUMNS = [
    "candidate_id",
    "registry_id",
    "business_name",
    "person_name",
    "job_title",
    "role_category",
    "evidence_url",
    "source_type",
    "entity_match_evidence",
    "notes",
]


PALBEC_ROWS = [
    {
        "candidate_id": "QC-DM-008",
        "registry_id": "1182557067",
        "business_name": "PALBEC INC.",
        "person_name": "Johanne Beaudoin",
        "job_title": "Founder",
        "role_category": "FOUNDER",
        "evidence_url": (
            "https://www.st-apollinaire.com/"
            "entreprises-organismes/name/"
            "industries-palbec-inc-les/"
        ),
        "source_type": "OFFICIAL_ORGANIZATION_PAGE",
        "entity_match_evidence": (
            "Municipal business directory identifies "
            "Industries Palbec at 230 rue Industrielle, "
            "Saint-Apollinaire and states that the "
            "business was founded by Johanne and "
            "Andre Beaudoin."
        ),
        "notes": (
            "Public municipal evidence. "
            "Founder relationship explicitly stated."
        ),
    },
    {
        "candidate_id": "QC-DM-008",
        "registry_id": "1182557067",
        "business_name": "PALBEC INC.",
        "person_name": "André Beaudoin",
        "job_title": "Founder",
        "role_category": "FOUNDER",
        "evidence_url": (
            "https://www.st-apollinaire.com/"
            "entreprises-organismes/name/"
            "industries-palbec-inc-les/"
        ),
        "source_type": "OFFICIAL_ORGANIZATION_PAGE",
        "entity_match_evidence": (
            "Municipal business directory identifies "
            "Industries Palbec at 230 rue Industrielle, "
            "Saint-Apollinaire and states that the "
            "business was founded by Johanne and "
            "Andre Beaudoin."
        ),
        "notes": (
            "Public municipal evidence. "
            "Founder relationship explicitly stated."
        ),
    },
]


def clean(value: str | None) -> str:
    return (value or "").strip()


def main() -> None:

    print(
        "=== V4 VERIFIED DECISION-MAKER SEED ==="
    )
    print()

    if not RESEARCH_FILE.exists():
        raise FileNotFoundError(
            f"Research file not found: {RESEARCH_FILE}"
        )

    # ---------------------------------------------
    # Load existing research template
    # ---------------------------------------------

    with RESEARCH_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        reader = csv.DictReader(handle)

        existing_rows = list(reader)

    print(
        f"Existing research rows : "
        f"{len(existing_rows):,}"
    )

    # ---------------------------------------------
    # Preserve all candidates except the blank
    # PALBEC placeholder.
    #
    # If PALBEC has already been seeded previously,
    # remove those rows first so rerunning this
    # script remains idempotent.
    # ---------------------------------------------

    preserved_rows = []

    removed_palbec_rows = 0

    for row in existing_rows:

        candidate_id = clean(
            row.get("candidate_id")
        )

        if candidate_id == "QC-DM-008":
            removed_palbec_rows += 1
            continue

        preserved_rows.append(
            {
                column: clean(row.get(column))
                for column in COLUMNS
            }
        )

    # ---------------------------------------------
    # Insert verified PALBEC rows
    # ---------------------------------------------

    final_rows = []

    inserted = False

    for row in preserved_rows:

        final_rows.append(row)

        # Insert PALBEC after QC-DM-007 so the
        # candidate ordering remains readable.
        if (
            clean(row.get("candidate_id"))
            == "QC-DM-007"
            and not inserted
        ):

            final_rows.extend(
                PALBEC_ROWS
            )

            inserted = True

    # Safety fallback if QC-DM-007 was unavailable.
    if not inserted:
        final_rows.extend(
            PALBEC_ROWS
        )

    # ---------------------------------------------
    # Write research file
    # ---------------------------------------------

    with RESEARCH_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=COLUMNS,
        )

        writer.writeheader()

        writer.writerows(
            final_rows
        )

    # ---------------------------------------------
    # Verification
    # ---------------------------------------------

    with RESEARCH_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        verify_rows = list(
            csv.DictReader(handle)
        )

    verified_palbec = [
        row
        for row in verify_rows
        if clean(row.get("candidate_id"))
        == "QC-DM-008"
        and clean(row.get("person_name"))
    ]

    blank_rows = [
        row
        for row in verify_rows
        if not clean(row.get("person_name"))
        and not clean(row.get("job_title"))
        and not clean(row.get("evidence_url"))
    ]

    print(
        f"Removed old PALBEC rows: "
        f"{removed_palbec_rows:,}"
    )

    print(
        f"Inserted verified rows : "
        f"{len(verified_palbec):,}"
    )

    print(
        f"Total research rows    : "
        f"{len(verify_rows):,}"
    )

    print(
        f"Blank candidate rows   : "
        f"{len(blank_rows):,}"
    )

    print()
    print("Verified sample:")
    print()

    for row in verified_palbec:

        print(
            f"  {row['candidate_id']} | "
            f"{row['business_name']} | "
            f"{row['person_name']} | "
            f"{row['job_title']}"
        )

    print()
    print(
        f"Research file          : "
        f"{RESEARCH_FILE}"
    )

    print()
    print(
        "=== V4 VERIFIED DECISION-MAKER "
        "SEED SUCCESS ==="
    )


if __name__ == "__main__":
    main()