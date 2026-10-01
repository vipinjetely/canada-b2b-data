from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

V4_DATA = (
    ROOT
    / "data"
    / "processed"
    / "v4"
)

AUDIT_FILE = (
    V4_DATA
    / "audit"
    / "karan_six_point_validation.json"
)

OUTPUT_DIR = (
    V4_DATA
    / "handover"
)

OUTPUT_JSON = (
    OUTPUT_DIR
    / "karan_v4_handover_summary.json"
)

OUTPUT_MD = (
    OUTPUT_DIR
    / "karan_v4_handover_summary.md"
)


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )


def get_result(
    report: dict,
    point_number: int,
) -> dict:

    for item in report.get("results", []):
        if item.get("point") == point_number:
            return item

    raise KeyError(
        f"Point #{point_number} not found in audit report."
    )


def fmt(value) -> str:

    if isinstance(value, bool):
        return "YES" if value else "NO"

    if isinstance(value, int):
        return f"{value:,}"

    if value is None:
        return "N/A"

    return str(value)


def main() -> None:

    print("=== V4 KARAN HANDOVER SUMMARY BUILD ===")
    print()

    require_file(AUDIT_FILE)

    report = json.loads(
        AUDIT_FILE.read_text(
            encoding="utf-8"
        )
    )

    if report.get("overall_status") != "PASS":
        raise RuntimeError(
            "Final six-point audit is not PASS. "
            "Handover summary will not be generated."
        )

    if report.get("points_passed") != 6:
        raise RuntimeError(
            "Expected 6 passed points before handover."
        )

    p1 = get_result(report, 1)
    p2 = get_result(report, 2)
    p3 = get_result(report, 3)
    p4 = get_result(report, 4)
    p5 = get_result(report, 5)
    p6 = get_result(report, 6)

    e1 = p1["evidence"]
    e2 = p2["evidence"]
    e3 = p3["evidence"]
    e4 = p4["evidence"]
    e5 = p5["evidence"]
    e6 = p6["evidence"]

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    built_at = datetime.now(
        timezone.utc
    ).isoformat()

    limitations = [
        (
            "Quebec new-business results are constrained by "
            "the freshness of the official source dataset. "
            f"The latest registration date currently present "
            f"is {e2.get('latest_source_date')}, with a "
            f"{e2.get('source_lag_days')}-day source lag "
            f"at validation time."
        ),
        (
            "Calendar last-7-day and last-30-day results must "
            "not be confused with dataset-relative windows. "
            "Both are reported separately."
        ),
        (
            "Decision-maker enrichment is evidence-first and "
            "currently demonstrates a verified sample rather "
            "than claiming complete decision-maker coverage "
            "for all businesses."
        ),
        (
            "Decision-maker names and titles are accepted only "
            "when supported by a reachable public evidence URL; "
            "generated or guessed people/titles are prohibited."
        ),
        (
            "Website cleanup quarantines directory, social, "
            "search/map and other blocked website values while "
            "preserving the underlying business records."
        ),
        (
            "Alberta official registry search access was audited "
            "as restricted/search-based; no public bulk dump or "
            "confirmed public API was treated as available."
        ),
    ]

    summary = {
        "project": "Canada B2B Business Data Automation System",
        "version": "V4",
        "handover_built_at_utc": built_at,
        "source_audit": str(AUDIT_FILE),
        "overall_status": report.get(
            "overall_status"
        ),
        "points_passed": report.get(
            "points_passed"
        ),
        "points_failed": report.get(
            "points_failed"
        ),
        "requirements": {
            "1_registry_integration": {
                "status": p1["status"],
                "quebec_registry_records":
                    e1.get(
                        "quebec_registry_records"
                    ),
                "unique_registry_ids":
                    e1.get(
                        "quebec_unique_registry_ids"
                    ),
                "duplicate_registry_ids":
                    e1.get(
                        "quebec_duplicate_registry_ids"
                    ),
            },
            "2_new_business_detection": {
                "status": p2["status"],
                "calendar_today":
                    e2.get("calendar_today"),
                "latest_source_date":
                    e2.get("latest_source_date"),
                "source_lag_days":
                    e2.get("source_lag_days"),
                "calendar_today_count":
                    e2.get(
                        "calendar_today_count"
                    ),
                "calendar_last_7_days":
                    e2.get(
                        "calendar_last_7_days"
                    ),
                "calendar_last_30_days":
                    e2.get(
                        "calendar_last_30_days"
                    ),
                "dataset_relative_last_7_days":
                    e2.get(
                        "dataset_relative_last_7_days"
                    ),
                "dataset_relative_last_30_days":
                    e2.get(
                        "dataset_relative_last_30_days"
                    ),
            },
            "3_employee_size": {
                "status": p3["status"],
                "registry_records":
                    e3.get("registry_records"),
                "verified_employee_ranges":
                    e3.get(
                        "verified_employee_ranges"
                    ),
                "records_with_employee_bucket":
                    e3.get(
                        "records_with_employee_bucket"
                    ),
            },
            "4_decision_makers": {
                "status": p4["status"],
                "accepted_decision_makers":
                    e4.get(
                        "accepted_decision_makers"
                    ),
                "covered_business_entities":
                    e4.get(
                        "covered_business_entities"
                    ),
                "missing_person_name":
                    e4.get(
                        "missing_person_name"
                    ),
                "missing_job_title":
                    e4.get(
                        "missing_job_title"
                    ),
                "missing_evidence_url":
                    e4.get(
                        "missing_evidence_url"
                    ),
            },
            "5_field_level_provenance": {
                "status": p5["status"],
                "registry_entities":
                    e5.get(
                        "registry_entities"
                    ),
                "registry_field_evidence_rows":
                    e5.get(
                        "registry_field_evidence_rows"
                    ),
                "registry_missing_source_url":
                    e5.get(
                        "registry_missing_source_url"
                    ),
                "registry_missing_last_verified":
                    e5.get(
                        "registry_missing_last_verified"
                    ),
                "decision_entities":
                    e5.get(
                        "decision_entities"
                    ),
                "decision_field_evidence_rows":
                    e5.get(
                        "decision_field_evidence_rows"
                    ),
                "decision_missing_source_url":
                    e5.get(
                        "decision_missing_source_url"
                    ),
                "decision_missing_last_verified":
                    e5.get(
                        "decision_missing_last_verified"
                    ),
            },
            "6_website_quality": {
                "status": p6["status"],
                "source_rows":
                    e6.get("source_rows"),
                "cleaned_rows":
                    e6.get("cleaned_rows"),
                "row_count_preserved":
                    e6.get(
                        "row_count_preserved"
                    ),
                "websites_before":
                    e6.get("websites_before"),
                "websites_after":
                    e6.get("websites_after"),
                "websites_quarantined":
                    e6.get(
                        "websites_quarantined"
                    ),
                "blocked_domains_remaining":
                    e6.get(
                        "blocked_domains_remaining"
                    ),
                "karan_flagged_categories":
                    e6.get(
                        "karan_flagged_categories"
                    ),
            },
        },
        "limitations": limitations,
        "evidence_paths": {
            "master_validation":
                str(AUDIT_FILE),
            "quebec_registry":
                str(
                    V4_DATA
                    / "registry"
                    / "quebec_registry.parquet"
                ),
            "new_business_audit":
                str(
                    V4_DATA
                    / "new_businesses"
                    / "quebec_new_business_detection.json"
                ),
            "decision_maker_sample":
                str(
                    V4_DATA
                    / "enrichment"
                    / "decision_maker_sample.csv"
                ),
            "decision_maker_evidence":
                str(
                    V4_DATA
                    / "enrichment"
                    / "decision_maker_sample_evidence.json"
                ),
            "registry_provenance":
                str(
                    V4_DATA
                    / "provenance"
                    / "quebec_field_provenance.parquet"
                ),
            "decision_maker_provenance":
                str(
                    V4_DATA
                    / "provenance"
                    / "decision_maker_field_provenance.parquet"
                ),
            "website_clean":
                str(
                    V4_DATA
                    / "website_quality"
                    / "business_locations_websites_cleaned.parquet"
                ),
            "website_quarantine":
                str(
                    V4_DATA
                    / "website_quality"
                    / "website_quarantine.parquet"
                ),
        },
    }

    OUTPUT_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    md = f"""# Canada B2B Data Automation System — V4 Handover

## Final Validation

**Overall status:** {report['overall_status']}

**Requirements passed:** {report['points_passed']}/6

**Requirements failed:** {report['points_failed']}/6

The V4 pipeline has been validated against the six defined requirements using the automated master audit.

## 1. Registry Integration

- Status: **{p1['status']}**
- Quebec registry records: **{fmt(e1.get('quebec_registry_records'))}**
- Unique registry IDs: **{fmt(e1.get('quebec_unique_registry_ids'))}**
- Duplicate registry IDs: **{fmt(e1.get('quebec_duplicate_registry_ids'))}**

## 2. New-Business Detection and Freshness

- Status: **{p2['status']}**
- Calendar validation date: **{fmt(e2.get('calendar_today'))}**
- Latest source registration date: **{fmt(e2.get('latest_source_date'))}**
- Source lag: **{fmt(e2.get('source_lag_days'))} days**
- Calendar today: **{fmt(e2.get('calendar_today_count'))}**
- Calendar last 7 days: **{fmt(e2.get('calendar_last_7_days'))}**
- Calendar last 30 days: **{fmt(e2.get('calendar_last_30_days'))}**
- Latest dataset-relative 7 days: **{fmt(e2.get('dataset_relative_last_7_days'))}**
- Latest dataset-relative 30 days: **{fmt(e2.get('dataset_relative_last_30_days'))}**

## 3. Employee-Size Classification

- Status: **{p3['status']}**
- Registry records: **{fmt(e3.get('registry_records'))}**
- Verified employee ranges: **{fmt(e3.get('verified_employee_ranges'))}**
- Records with employee-size bucket: **{fmt(e3.get('records_with_employee_bucket'))}**

Employee size is retained as evidence-backed registry ranges rather than converting ranges into invented exact employee counts.

## 4. Evidence-Backed Decision Makers

- Status: **{p4['status']}**
- Verified decision-makers demonstrated: **{fmt(e4.get('accepted_decision_makers'))}**
- Covered business entities: **{fmt(e4.get('covered_business_entities'))}**
- Missing person names: **{fmt(e4.get('missing_person_name'))}**
- Missing job titles: **{fmt(e4.get('missing_job_title'))}**
- Missing evidence URLs: **{fmt(e4.get('missing_evidence_url'))}**

The decision-maker workflow rejects generated people, generated titles, unsupported role categories, unsupported source types and unreachable evidence URLs.

## 5. Field-Level Provenance

- Status: **{p5['status']}**
- Registry entities: **{fmt(e5.get('registry_entities'))}**
- Registry field-evidence rows: **{fmt(e5.get('registry_field_evidence_rows'))}**
- Missing registry source URLs: **{fmt(e5.get('registry_missing_source_url'))}**
- Missing registry verification timestamps: **{fmt(e5.get('registry_missing_last_verified'))}**
- Decision-maker entities: **{fmt(e5.get('decision_entities'))}**
- Decision-maker field-evidence rows: **{fmt(e5.get('decision_field_evidence_rows'))}**
- Missing decision-maker source URLs: **{fmt(e5.get('decision_missing_source_url'))}**
- Missing decision-maker verification timestamps: **{fmt(e5.get('decision_missing_last_verified'))}**

## 6. Website Quality Cleanup

- Status: **{p6['status']}**
- Business rows before/after: **{fmt(e6.get('source_rows'))} / {fmt(e6.get('cleaned_rows'))}**
- Row count preserved: **{fmt(e6.get('row_count_preserved'))}**
- Nonblank websites before: **{fmt(e6.get('websites_before'))}**
- Nonblank websites after: **{fmt(e6.get('websites_after'))}**
- Website values quarantined: **{fmt(e6.get('websites_quarantined'))}**
- Blocked website values remaining: **{fmt(e6.get('blocked_domains_remaining'))}**
- Karan-flagged categories detected: **{fmt(e6.get('karan_flagged_categories'))}**

Underlying business records are preserved; rejected website values are quarantined rather than deleting businesses.

## Known Limitations

1. {limitations[0]}
2. {limitations[1]}
3. {limitations[2]}
4. {limitations[3]}
5. {limitations[4]}
6. {limitations[5]}

## Validation Evidence

Master validation:

`{AUDIT_FILE}`

Quebec registry:

`{V4_DATA / 'registry' / 'quebec_registry.parquet'}`

New-business evidence:

`{V4_DATA / 'new_businesses' / 'quebec_new_business_detection.json'}`

Decision-maker sample:

`{V4_DATA / 'enrichment' / 'decision_maker_sample.csv'}`

Decision-maker evidence:

`{V4_DATA / 'enrichment' / 'decision_maker_sample_evidence.json'}`

Registry field provenance:

`{V4_DATA / 'provenance' / 'quebec_field_provenance.parquet'}`

Decision-maker field provenance:

`{V4_DATA / 'provenance' / 'decision_maker_field_provenance.parquet'}`

Clean website dataset:

`{V4_DATA / 'website_quality' / 'business_locations_websites_cleaned.parquet'}`

Website quarantine:

`{V4_DATA / 'website_quality' / 'website_quarantine.parquet'}`

---

Generated from the final automated V4 validation evidence.

Generated at UTC: `{built_at}`
"""

    OUTPUT_MD.write_text(
        md,
        encoding="utf-8",
    )

    print("Final audit status     :", report["overall_status"])
    print("Requirements passed    :", f"{report['points_passed']}/6")
    print()

    print(
        "Quebec registry records:",
        fmt(
            e1.get(
                "quebec_registry_records"
            )
        ),
    )

    print(
        "Decision-makers        :",
        fmt(
            e4.get(
                "accepted_decision_makers"
            )
        ),
    )

    print(
        "Provenance rows        :",
        fmt(
            e5.get(
                "registry_field_evidence_rows"
            )
        ),
    )

    print(
        "Websites quarantined   :",
        fmt(
            e6.get(
                "websites_quarantined"
            )
        ),
    )

    print(
        "Blocked remaining      :",
        fmt(
            e6.get(
                "blocked_domains_remaining"
            )
        ),
    )

    print()
    print("JSON handover :", OUTPUT_JSON)
    print("Markdown      :", OUTPUT_MD)
    print()

    print(
        "=== V4 KARAN HANDOVER SUMMARY SUCCESS ==="
    )


if __name__ == "__main__":
    main()