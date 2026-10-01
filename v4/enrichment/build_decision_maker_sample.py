from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "enrichment"
    / "decision_maker_input.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "v4"
    / "enrichment"
)

OUTPUT = OUTPUT_DIR / "decision_maker_sample.csv"

EVIDENCE = (
    OUTPUT_DIR
    / "decision_maker_sample_evidence.json"
)

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

ALLOWED_SOURCE_TYPES = {
    "COMPANY_WEBSITE",
    "OFFICIAL_ORGANIZATION_PAGE",
    "GOVERNMENT_SOURCE",
    "PUBLIC_PROFESSIONAL_PROFILE",
}

REQUIRED_COLUMNS = [
    "registry_id",
    "business_name",
    "person_name",
    "job_title",
    "role_category",
    "evidence_url",
    "source_type",
]


def clean(value: str | None) -> str:
    return (value or "").strip()


def normalize_role(value: str) -> str:
    return (
        clean(value)
        .upper()
        .replace("&", "AND")
        .replace("-", "_")
        .replace(" ", "_")
    )


def valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)

        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
        )

    except ValueError:
        return False


def probe_url(url: str) -> dict:
    checked_at = datetime.now(
        timezone.utc
    ).isoformat()

    try:
        response = requests.get(
            url,
            timeout=(10, 25),
            allow_redirects=True,
            stream=True,
            headers={
                "User-Agent":
                    "Canada-B2B-Data-Automation/4.0"
            },
        )

        result = {
            "checked_at_utc": checked_at,
            "reachable": (
                200 <= response.status_code < 400
            ),
            "http_status": response.status_code,
            "final_url": response.url,
            "content_type":
                response.headers.get("Content-Type"),
        }

        response.close()
        return result

    except requests.RequestException as exc:
        return {
            "checked_at_utc": checked_at,
            "reachable": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def create_template() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with INPUT.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        writer = csv.writer(handle)

        writer.writerow(
            REQUIRED_COLUMNS
            + [
                "notes",
            ]
        )


def main() -> None:
    print(
        "=== V4 DECISION-MAKER "
        "EVIDENCE BUILDER ==="
    )
    print()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not INPUT.exists():
        create_template()

        print(
            "Input template created:"
        )
        print(INPUT)
        print()
        print(
            "Populate this file only with "
            "decision-makers supported by a "
            "public evidence URL."
        )
        print()
        print(
            "No guessed/generated contacts "
            "will be accepted."
        )
        return

    with INPUT.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        reader = csv.DictReader(handle)

        headers = reader.fieldnames or []

        missing_columns = [
            column
            for column in REQUIRED_COLUMNS
            if column not in headers
        ]

        if missing_columns:
            raise RuntimeError(
                "Input CSV missing columns: "
                + ", ".join(missing_columns)
            )

        source_rows = list(reader)

    if not source_rows:
        print(
            "Input exists but contains no "
            "decision-maker rows."
        )
        print()
        print(f"Input: {INPUT}")
        return

    accepted = []
    rejected = []

    seen = set()

    for index, row in enumerate(
        source_rows,
        start=2,
    ):
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

        role_category = normalize_role(
            row.get("role_category", "")
        )

        evidence_url = clean(
            row.get("evidence_url")
        )

        source_type = normalize_role(
            row.get("source_type", "")
        )

        notes = clean(
            row.get("notes")
        )

        reasons = []

        if not registry_id:
            reasons.append(
                "missing registry_id"
            )

        if not business_name:
            reasons.append(
                "missing business_name"
            )

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

        if source_type not in ALLOWED_SOURCE_TYPES:
            reasons.append(
                "unsupported source_type"
            )

        if not valid_http_url(evidence_url):
            reasons.append(
                "invalid evidence_url"
            )

        dedupe_key = (
            registry_id.lower(),
            person_name.lower(),
            job_title.lower(),
        )

        if dedupe_key in seen:
            reasons.append(
                "duplicate decision-maker"
            )

        if reasons:
            rejected.append(
                {
                    "input_line": index,
                    "registry_id": registry_id,
                    "business_name": business_name,
                    "person_name": person_name,
                    "job_title": job_title,
                    "reasons": reasons,
                }
            )
            continue

        probe = probe_url(evidence_url)

        if not probe.get("reachable"):
            rejected.append(
                {
                    "input_line": index,
                    "registry_id": registry_id,
                    "business_name": business_name,
                    "person_name": person_name,
                    "job_title": job_title,
                    "reasons": [
                        "evidence URL not reachable"
                    ],
                    "url_probe": probe,
                }
            )
            continue

        seen.add(dedupe_key)

        accepted.append(
            {
                "registry_id": registry_id,
                "business_name": business_name,
                "person_name": person_name,
                "job_title": job_title,
                "role_category":
                    role_category,
                "source_type":
                    source_type,
                "evidence_url":
                    evidence_url,
                "evidence_final_url":
                    probe.get("final_url"),
                "evidence_http_status":
                    probe.get("http_status"),
                "verified_at_utc":
                    probe.get(
                        "checked_at_utc"
                    ),
                "verification_method":
                    "PUBLIC_SOURCE_EVIDENCE",
                "confidence":
                    "CONFIRMED_PUBLIC_SOURCE",
                "notes": notes,
            }
        )

    output_columns = [
        "registry_id",
        "business_name",
        "person_name",
        "job_title",
        "role_category",
        "source_type",
        "evidence_url",
        "evidence_final_url",
        "evidence_http_status",
        "verified_at_utc",
        "verification_method",
        "confidence",
        "notes",
    ]

    with OUTPUT.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=output_columns,
        )

        writer.writeheader()
        writer.writerows(accepted)

    evidence = {
        "built_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "input_file":
            str(INPUT),

        "output_file":
            str(OUTPUT),

        "input_rows":
            len(source_rows),

        "accepted_rows":
            len(accepted),

        "rejected_rows":
            len(rejected),

        "policy": {
            "generated_people_allowed":
                False,

            "generated_titles_allowed":
                False,

            "evidence_url_required":
                True,

            "public_source_required":
                True,

            "verification_timestamp_required":
                True,
        },

        "target_roles":
            sorted(TARGET_ROLES),

        "allowed_source_types":
            sorted(ALLOWED_SOURCE_TYPES),

        "rejections":
            rejected,
    }

    EVIDENCE.write_text(
        json.dumps(
            evidence,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"Input rows    : {len(source_rows):,}")
    print(f"Accepted      : {len(accepted):,}")
    print(f"Rejected      : {len(rejected):,}")
    print()
    print(f"Output        : {OUTPUT}")
    print(f"Evidence      : {EVIDENCE}")
    print()
    print(
        "=== V4 DECISION-MAKER "
        "EVIDENCE BUILD SUCCESS ==="
    )


if __name__ == "__main__":
    main()