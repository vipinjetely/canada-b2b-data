from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

V4_DATA = ROOT / "data" / "processed" / "v4"

AUDIT_FILE = (
    V4_DATA
    / "audit"
    / "karan_six_point_validation.json"
)

HANDOVER_JSON = (
    V4_DATA
    / "handover"
    / "karan_v4_handover_summary.json"
)

HANDOVER_MD = (
    V4_DATA
    / "handover"
    / "karan_v4_handover_summary.md"
)

REQUIRED_ARTIFACTS = {
    "Quebec registry": (
        V4_DATA
        / "registry"
        / "quebec_registry.parquet"
    ),
    "New-business evidence": (
        V4_DATA
        / "new_businesses"
        / "quebec_new_business_detection.json"
    ),
    "Decision-maker sample": (
        V4_DATA
        / "enrichment"
        / "decision_maker_sample.csv"
    ),
    "Decision-maker evidence": (
        V4_DATA
        / "enrichment"
        / "decision_maker_sample_evidence.json"
    ),
    "Registry provenance": (
        V4_DATA
        / "provenance"
        / "quebec_field_provenance.parquet"
    ),
    "Decision-maker provenance": (
        V4_DATA
        / "provenance"
        / "decision_maker_field_provenance.parquet"
    ),
    "Clean website dataset": (
        V4_DATA
        / "website_quality"
        / "business_locations_websites_cleaned.parquet"
    ),
    "Website quarantine": (
        V4_DATA
        / "website_quality"
        / "website_quarantine.parquet"
    ),
    "Website cleanup audit": (
        V4_DATA
        / "website_quality"
        / "website_cleanup_audit.json"
    ),
    "Handover JSON": HANDOVER_JSON,
    "Handover Markdown": HANDOVER_MD,
}


def fail(message: str) -> None:
    print()
    print("V4 DEMO STATUS : FAIL")
    print(f"Reason         : {message}")
    sys.exit(1)


def load_json(path: Path) -> dict:
    if not path.exists():
        fail(
            f"Required JSON not found: {path}"
        )

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        fail(
            f"Could not read {path.name}: {exc}"
        )

    return {}


def get_point(
    report: dict,
    number: int,
) -> dict:

    for item in report.get(
        "results",
        []
    ):
        if item.get("point") == number:
            return item

    fail(
        f"Point #{number} missing "
        "from master audit."
    )

    return {}


def fmt(value) -> str:
    if isinstance(value, bool):
        return "YES" if value else "NO"

    if isinstance(value, int):
        return f"{value:,}"

    if value is None:
        return "N/A"

    return str(value)


def main() -> None:

    print()
    print("=" * 72)
    print(
        "CANADA B2B BUSINESS DATA "
        "AUTOMATION SYSTEM"
    )
    print("V4 VALIDATION DEMO")
    print("=" * 72)
    print()

    # --------------------------------------------------
    # 1. Check master audit
    # --------------------------------------------------

    audit = load_json(
        AUDIT_FILE
    )

    overall = audit.get(
        "overall_status"
    )

    passed = audit.get(
        "points_passed"
    )

    failed = audit.get(
        "points_failed"
    )

    total = audit.get(
        "total_points"
    )

    if overall != "PASS":
        fail(
            "Master audit overall_status "
            "is not PASS."
        )

    if passed != 6:
        fail(
            f"Expected 6 passed points; "
            f"found {passed}."
        )

    if failed != 0:
        fail(
            f"Expected zero failed points; "
            f"found {failed}."
        )

    if total != 6:
        fail(
            f"Expected six validation "
            f"points; found {total}."
        )

    # --------------------------------------------------
    # 2. Check each requirement
    # --------------------------------------------------

    points = []

    for number in range(1, 7):

        item = get_point(
            audit,
            number,
        )

        if item.get("status") != "PASS":
            fail(
                f"Point #{number} is not PASS."
            )

        points.append(item)

    # --------------------------------------------------
    # 3. Check handover summary
    # --------------------------------------------------

    handover = load_json(
        HANDOVER_JSON
    )

    if (
        handover.get(
            "overall_status"
        )
        != "PASS"
    ):
        fail(
            "Handover summary is not PASS."
        )

    if (
        handover.get(
            "points_passed"
        )
        != 6
    ):
        fail(
            "Handover summary does not "
            "show 6 passed points."
        )

    # --------------------------------------------------
    # 4. Check required evidence artifacts
    # --------------------------------------------------

    missing = []

    empty = []

    for label, path in (
        REQUIRED_ARTIFACTS.items()
    ):

        if not path.exists():
            missing.append(
                f"{label}: {path}"
            )
            continue

        if path.is_file():
            if path.stat().st_size == 0:
                empty.append(
                    f"{label}: {path}"
                )

    if missing:
        fail(
            "Missing required artifact(s): "
            + " | ".join(missing)
        )

    if empty:
        fail(
            "Empty required artifact(s): "
            + " | ".join(empty)
        )

    # --------------------------------------------------
    # 5. Extract evidence
    # --------------------------------------------------

    p1 = points[0]["evidence"]
    p2 = points[1]["evidence"]
    p3 = points[2]["evidence"]
    p4 = points[3]["evidence"]
    p5 = points[4]["evidence"]
    p6 = points[5]["evidence"]

    # --------------------------------------------------
    # 6. Cross-check key invariants
    # --------------------------------------------------

    if (
        p1.get(
            "quebec_duplicate_registry_ids"
        )
        != 0
    ):
        fail(
            "Quebec registry contains "
            "duplicate registry IDs."
        )

    if (
        p4.get(
            "missing_person_name"
        )
        != 0
    ):
        fail(
            "Decision-maker sample has "
            "missing person names."
        )

    if (
        p4.get(
            "missing_job_title"
        )
        != 0
    ):
        fail(
            "Decision-maker sample has "
            "missing job titles."
        )

    if (
        p4.get(
            "missing_evidence_url"
        )
        != 0
    ):
        fail(
            "Decision-maker sample has "
            "missing evidence URLs."
        )

    if (
        p5.get(
            "registry_missing_source_url"
        )
        != 0
    ):
        fail(
            "Registry provenance has "
            "missing source URLs."
        )

    if (
        p5.get(
            "registry_missing_last_verified"
        )
        != 0
    ):
        fail(
            "Registry provenance has "
            "missing verification timestamps."
        )

    if (
        p5.get(
            "decision_missing_source_url"
        )
        != 0
    ):
        fail(
            "Decision-maker provenance has "
            "missing source URLs."
        )

    if (
        p5.get(
            "decision_missing_last_verified"
        )
        != 0
    ):
        fail(
            "Decision-maker provenance has "
            "missing verification timestamps."
        )

    if (
        p6.get(
            "blocked_domains_remaining"
        )
        != 0
    ):
        fail(
            "Blocked website values "
            "remain in cleaned output."
        )

    if (
        p6.get(
            "row_count_preserved"
        )
        is not True
    ):
        fail(
            "Website cleanup did not "
            "preserve business row count."
        )

    # --------------------------------------------------
    # 7. Print six-point demo
    # --------------------------------------------------

    print("SIX REQUIREMENTS")
    print("-" * 72)

    for item in points:
        print(
            f"[PASS] Point #{item['point']} - "
            f"{item['title']}"
        )

    print("-" * 72)
    print()

    # --------------------------------------------------
    # 8. Headline evidence
    # --------------------------------------------------

    print("HEADLINE EVIDENCE")
    print("-" * 72)

    print(
        "Quebec registry records          :",
        fmt(
            p1.get(
                "quebec_registry_records"
            )
        ),
    )

    print(
        "Duplicate Quebec registry IDs    :",
        fmt(
            p1.get(
                "quebec_duplicate_registry_ids"
            )
        ),
    )

    print(
        "Latest registration date         :",
        fmt(
            p2.get(
                "latest_source_date"
            )
        ),
    )

    print(
        "Source freshness lag             :",
        f"{fmt(p2.get('source_lag_days'))} day(s)",
    )

    print(
        "Latest dataset 7-day businesses  :",
        fmt(
            p2.get(
                "dataset_relative_last_7_days"
            )
        ),
    )

    print(
        "Latest dataset 30-day businesses :",
        fmt(
            p2.get(
                "dataset_relative_last_30_days"
            )
        ),
    )

    print(
        "Verified employee ranges         :",
        fmt(
            p3.get(
                "verified_employee_ranges"
            )
        ),
    )

    print(
        "Decision-makers demonstrated     :",
        fmt(
            p4.get(
                "accepted_decision_makers"
            )
        ),
    )

    print(
        "Decision-maker companies covered :",
        fmt(
            p4.get(
                "covered_business_entities"
            )
        ),
    )

    print(
        "Registry provenance rows         :",
        fmt(
            p5.get(
                "registry_field_evidence_rows"
            )
        ),
    )

    print(
        "Missing provenance source URLs   :",
        fmt(
            p5.get(
                "registry_missing_source_url"
            )
        ),
    )

    print(
        "Missing provenance timestamps    :",
        fmt(
            p5.get(
                "registry_missing_last_verified"
            )
        ),
    )

    print(
        "Websites quarantined             :",
        fmt(
            p6.get(
                "websites_quarantined"
            )
        ),
    )

    print(
        "Blocked websites remaining       :",
        fmt(
            p6.get(
                "blocked_domains_remaining"
            )
        ),
    )

    print(
        "Business rows preserved          :",
        fmt(
            p6.get(
                "cleaned_rows"
            )
        ),
    )

    print("-" * 72)
    print()

    # --------------------------------------------------
    # 9. Evidence artifact check
    # --------------------------------------------------

    print("EVIDENCE ARTIFACTS")
    print("-" * 72)

    for label, path in (
        REQUIRED_ARTIFACTS.items()
    ):

        size = path.stat().st_size

        print(
            f"[OK] {label:<28} "
            f"{size:>12,} bytes"
        )

    print("-" * 72)
    print()

    # --------------------------------------------------
    # Final
    # --------------------------------------------------

    print("=" * 72)
    print("V4 DEMO STATUS : PASS")
    print("Requirements   : 6/6")
    print("Evidence       : PRESENT")
    print("Core rebuild   : NOT REQUIRED")
    print("=" * 72)
    print()

    print(
        "Master audit :",
        AUDIT_FILE,
    )

    print(
        "Handover     :",
        HANDOVER_MD,
    )

    print()


if __name__ == "__main__":
    main()