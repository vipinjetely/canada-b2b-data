from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

RESEARCH_FILE = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "enrichment"
    / "decision_maker_research.csv"
)


NEW_RECORD = {
    "candidate_id": "QC-DM-009",
    "registry_id": "1182555814",
    "business_name": "Technologies de voyage Zii Inc.",
    "person_name": "Monique Mardinian",
    "job_title": "CEO & Founder",
    "role_category": "FOUNDER_EXECUTIVE",
    "evidence_url": (
        "https://www.financialexecutives.org/"
        "Events/Conferences/"
        "2019-Financial-Leadership-Summit/"
        "Info/Agenda.aspx"
    ),
    "source_type": "PUBLIC_PROFESSIONAL_ORGANIZATION",
    "entity_match_evidence": (
        "Quebec candidate Technologies de voyage Zii Inc. "
        "is the French legal name corresponding to "
        "Zii Travel Technologies Inc.; public Quebec "
        "business data identifies both names for the "
        "same registered entity. FEI identifies "
        "Monique Mardinian as CEO & Founder of "
        "Zii Travel Technologies, Inc."
    ),
    "notes": (
        "Evidence-backed decision-maker. "
        "No generated or inferred person/title."
    ),
}


FIELDNAMES = [
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


def main() -> None:

    print("=== V4 ZII VERIFIED DECISION-MAKER SEED ===")
    print()

    if not RESEARCH_FILE.exists():
        raise FileNotFoundError(
            f"Research file not found: {RESEARCH_FILE}"
        )

    with RESEARCH_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        reader = csv.DictReader(f)

        rows = list(reader)

    existing_rows = len(rows)

    # Remove an existing Zii / Monique row only.
    # This makes the script safe to rerun without duplicates.
    filtered_rows = []

    removed_existing = 0

    for row in rows:

        same_candidate = (
            row.get("candidate_id", "").strip()
            == NEW_RECORD["candidate_id"]
        )

        same_person = (
            row.get("person_name", "")
            .strip()
            .casefold()
            == NEW_RECORD["person_name"].casefold()
        )

        if same_candidate and same_person:
            removed_existing += 1
            continue

        filtered_rows.append(row)

    filtered_rows.append(NEW_RECORD)

    with RESEARCH_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=FIELDNAMES,
        )

        writer.writeheader()

        for row in filtered_rows:

            writer.writerow(
                {
                    field: row.get(field, "")
                    for field in FIELDNAMES
                }
            )

    print(
        f"Existing research rows : {existing_rows:,}"
    )

    print(
        f"Existing Zii row removed: {removed_existing:,}"
    )

    print(
        "Inserted verified rows : 1"
    )

    print(
        f"Total research rows    : {len(filtered_rows):,}"
    )

    print()
    print("Inserted evidence:")
    print()

    print(
        f"  {NEW_RECORD['candidate_id']} | "
        f"{NEW_RECORD['business_name']} | "
        f"{NEW_RECORD['person_name']} | "
        f"{NEW_RECORD['job_title']}"
    )

    print()
    print(
        f"Research file          : {RESEARCH_FILE}"
    )

    print()
    print(
        "=== V4 ZII VERIFIED DECISION-MAKER "
        "SEED SUCCESS ==="
    )


if __name__ == "__main__":
    main()