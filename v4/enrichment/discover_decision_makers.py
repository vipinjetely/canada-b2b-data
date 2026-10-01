from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]

BASE_DIR = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "enrichment"
)

CANDIDATES = BASE_DIR / "decision_maker_candidates.csv"

RESEARCH_INPUT = BASE_DIR / "decision_maker_research.csv"

BUILDER_INPUT = BASE_DIR / "decision_maker_input.csv"

AUDIT_OUTPUT = BASE_DIR / "decision_maker_discovery_audit.json"


RESEARCH_COLUMNS = [
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


TARGET_ROLES = {
    "OWNER",
    "FOUNDER",
    "CEO",
    "PRESIDENT",
    "GENERAL_MANAGER",
    "GM",
    "IT",
    "IT_MANAGER",
    "IT_DIRECTOR",
    "CIO",
    "CTO",
    "OPERATIONS",
    "OPERATIONS_MANAGER",
    "DIRECTOR_OPERATIONS",
    "PROCUREMENT",
    "PROCUREMENT_MANAGER",
    "PURCHASING_MANAGER",
}


SOURCE_TYPES = {
    "COMPANY_WEBSITE",
    "OFFICIAL_ORGANIZATION_PAGE",
    "GOVERNMENT_SOURCE",
    "PUBLIC_PROFESSIONAL_PROFILE",
}


def clean(value: str | None) -> str:
    return (value or "").strip()


def normalize(value: str | None) -> str:
    return (
        clean(value)
        .upper()
        .replace("&", "AND")
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "_")
    )


def valid_url(value: str) -> bool:
    try:
        parsed = urlparse(value)

        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
        )

    except ValueError:
        return False


def load_candidates() -> dict[str, dict]:
    if not CANDIDATES.exists():
        raise FileNotFoundError(
            f"Candidate file not found: {CANDIDATES}"
        )

    with CANDIDATES.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        rows = list(csv.DictReader(handle))

    return {
        clean(row["candidate_id"]): row
        for row in rows
    }


def create_research_template(
    candidates: dict[str, dict],
) -> None:

    with RESEARCH_INPUT.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=RESEARCH_COLUMNS,
        )

        writer.writeheader()

        for candidate_id, row in candidates.items():

            writer.writerow(
                {
                    "candidate_id":
                        candidate_id,

                    "registry_id":
                        clean(
                            row.get("registry_id")
                        ),

                    "business_name":
                        clean(
                            row.get("business_name")
                        ),

                    "person_name":
                        "",

                    "job_title":
                        "",

                    "role_category":
                        "",

                    "evidence_url":
                        "",

                    "source_type":
                        "",

                    "entity_match_evidence":
                        "",

                    "notes":
                        "",
                }
            )


def main() -> None:
    print(
        "=== V4 DECISION-MAKER DISCOVERY "
        "VALIDATION ==="
    )
    print()

    BASE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    candidates = load_candidates()

    print(
        f"Candidate companies : "
        f"{len(candidates):,}"
    )

    # --------------------------------------------------
    # First run:
    # create controlled research sheet.
    # --------------------------------------------------

    if not RESEARCH_INPUT.exists():

        create_research_template(
            candidates
        )

        print()
        print(
            "Research template created:"
        )
        print(RESEARCH_INPUT)

        print()
        print(
            "Populate only publicly evidenced "
            "decision-makers."
        )

        print(
            "Do NOT guess people or titles."
        )

        print()
        print(
            "=== RESEARCH TEMPLATE READY ==="
        )

        return

    # --------------------------------------------------
    # Read researched evidence
    # --------------------------------------------------

    with RESEARCH_INPUT.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        reader = csv.DictReader(handle)

        source_rows = list(reader)

    accepted = []
    rejected = []
    skipped_blank = []

    seen = set()

    for line_number, row in enumerate(
        source_rows,
        start=2,
    ):

        candidate_id = clean(
            row.get("candidate_id")
        )

        registry_id = clean(
            row.get("registry_id")
        )

        business_name = clean(
            row.get("business_name")
        )

        person_name = clean(
            row.get("person_name")
        )

        job_title = clean(
            row.get("job_title")
        )

        role_category = normalize(
            row.get("role_category")
        )

        evidence_url = clean(
            row.get("evidence_url")
        )

        source_type = normalize(
            row.get("source_type")
        )

        entity_match_evidence = clean(
            row.get("entity_match_evidence")
        )

        notes = clean(
            row.get("notes")
        )

        # ----------------------------------------------
        # Empty research row = not researched/confirmed
        # yet, not an error.
        # ----------------------------------------------

        if (
            not person_name
            and not job_title
            and not evidence_url
        ):
            skipped_blank.append(
                candidate_id
            )
            continue

        reasons = []

        # ----------------------------------------------
        # Candidate identity validation
        # ----------------------------------------------

        candidate = candidates.get(
            candidate_id
        )

        if candidate is None:

            reasons.append(
                "unknown candidate_id"
            )

        else:

            expected_registry_id = clean(
                candidate.get(
                    "registry_id"
                )
            )

            expected_business_name = clean(
                candidate.get(
                    "business_name"
                )
            )

            if (
                registry_id
                != expected_registry_id
            ):
                reasons.append(
                    "registry_id mismatch"
                )

            if (
                business_name
                != expected_business_name
            ):
                reasons.append(
                    "business_name mismatch"
                )

        # ----------------------------------------------
        # Decision-maker evidence validation
        # ----------------------------------------------

        if not person_name:
            reasons.append(
                "missing person_name"
            )

        if not job_title:
            reasons.append(
                "missing job_title"
            )

        if role_category not in TARGET_ROLES:
            reasons.append(
                "unsupported role_category"
            )

        if source_type not in SOURCE_TYPES:
            reasons.append(
                "unsupported source_type"
            )

        if not valid_url(
            evidence_url
        ):
            reasons.append(
                "invalid evidence_url"
            )

        if not entity_match_evidence:
            reasons.append(
                "missing entity_match_evidence"
            )

        dedupe_key = (
            registry_id.lower(),
            person_name.lower(),
            job_title.lower(),
        )

        if dedupe_key in seen:
            reasons.append(
                "duplicate person/title"
            )

        if reasons:

            rejected.append(
                {
                    "line":
                        line_number,

                    "candidate_id":
                        candidate_id,

                    "person_name":
                        person_name,

                    "job_title":
                        job_title,

                    "reasons":
                        reasons,
                }
            )

            continue

        seen.add(
            dedupe_key
        )

        accepted.append(
            {
                "registry_id":
                    registry_id,

                "business_name":
                    business_name,

                "person_name":
                    person_name,

                "job_title":
                    job_title,

                "role_category":
                    role_category,

                "evidence_url":
                    evidence_url,

                "source_type":
                    source_type,

                "notes":
                    (
                        f"Candidate={candidate_id}; "
                        f"Entity match="
                        f"{entity_match_evidence}"
                        + (
                            f"; {notes}"
                            if notes
                            else ""
                        )
                    ),
            }
        )

    # --------------------------------------------------
    # Write exact input format required by the existing
    # evidence builder.
    # --------------------------------------------------

    builder_columns = [
        "registry_id",
        "business_name",
        "person_name",
        "job_title",
        "role_category",
        "evidence_url",
        "source_type",
        "notes",
    ]

    with BUILDER_INPUT.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=builder_columns,
        )

        writer.writeheader()

        writer.writerows(
            accepted
        )

    audit = {
        "built_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "candidate_file":
            str(CANDIDATES),

        "research_file":
            str(RESEARCH_INPUT),

        "builder_input":
            str(BUILDER_INPUT),

        "candidate_companies":
            len(candidates),

        "research_rows":
            len(source_rows),

        "accepted_decision_makers":
            len(accepted),

        "rejected_rows":
            len(rejected),

        "blank_unresearched_rows":
            len(skipped_blank),

        "rules": {
            "generated_people":
                False,

            "generated_titles":
                False,

            "exact_candidate_match":
                True,

            "evidence_url_required":
                True,

            "entity_match_evidence_required":
                True,

            "target_role_required":
                True,
        },

        "rejected":
            rejected,
    }

    AUDIT_OUTPUT.write_text(
        json.dumps(
            audit,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        f"Research rows       : "
        f"{len(source_rows):,}"
    )

    print(
        f"Accepted            : "
        f"{len(accepted):,}"
    )

    print(
        f"Rejected            : "
        f"{len(rejected):,}"
    )

    print(
        f"Blank/unresearched  : "
        f"{len(skipped_blank):,}"
    )

    print()
    print(
        f"Builder input       : "
        f"{BUILDER_INPUT}"
    )

    print(
        f"Audit               : "
        f"{AUDIT_OUTPUT}"
    )

    print()
    print(
        "=== V4 DECISION-MAKER DISCOVERY "
        "VALIDATION SUCCESS ==="
    )


if __name__ == "__main__":
    main()