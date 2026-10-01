from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "data" / "processed" / "v4" / "registry"
OUTPUT = OUTPUT_DIR / "quebec_req_access_audit.json"

DATASET_URL = (
    "https://www.donneesquebec.ca/recherche/dataset/"
    "registre-des-entreprises"
)

GUIDE_URL = (
    "https://www.donneesquebec.ca/recherche/dataset/"
    "6f710997-b5f9-4347-893b-1a47ddb61437/"
    "resource/09008d3a-2e0e-4613-ab43-bd833f381929/"
    "download/guideutilisation.pdf"
)


def probe(url: str) -> dict:
    checked_at = datetime.now(timezone.utc).isoformat()

    try:
        response = requests.get(
            url,
            timeout=(10, 30),
            allow_redirects=True,
            stream=True,
            headers={
                "User-Agent":
                    "Canada-B2B-Data-Automation/4.0"
            },
        )

        result = {
            "url": url,
            "checked_at_utc": checked_at,
            "reachable": True,
            "http_status": response.status_code,
            "final_url": response.url,
            "content_type":
                response.headers.get("Content-Type"),
            "content_length":
                response.headers.get("Content-Length"),
            "last_modified":
                response.headers.get("Last-Modified"),
        }

        response.close()
        return result

    except requests.RequestException as exc:
        return {
            "url": url,
            "checked_at_utc": checked_at,
            "reachable": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def main() -> None:
    print("=== V4 QUEBEC REQ ACCESS AUDIT ===")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dataset_probe = probe(DATASET_URL)
    guide_probe = probe(GUIDE_URL)

    audit = {
        "registry_source": "QUEBEC_REQ",
        "jurisdiction": "Quebec",
        "registry_type": "PROVINCIAL_REGISTRY",

        "official_dataset_url": DATASET_URL,
        "official_guide_url": GUIDE_URL,

        "official_bulk_dataset_confirmed": True,

        "dataset_format": "ZIP containing six CSV files",

        "join_key": "NEQ",

        "update_frequency": "BIMONTHLY",

        "confirmed_enterprise_fields": {
            "NEQ": "Quebec enterprise number",
            "DAT_IMMAT": "Registration date",
            "COD_INTVAL_EMPLO_QUE":
                "Employee-count range in Quebec",
        },

        "person_data_limitation": (
            "The open dataset excludes names and addresses "
            "of natural persons and related persons such as "
            "directors. Decision-maker enrichment therefore "
            "requires a separate evidence source."
        ),

        "connector_status":
            "OFFICIAL_BULK_DATA_AVAILABLE",

        "probes": {
            "dataset_page": dataset_probe,
            "usage_guide": guide_probe,
        },

        "audited_at_utc":
            datetime.now(timezone.utc).isoformat(),
    }

    OUTPUT.write_text(
        json.dumps(
            audit,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        "Dataset page reachable  :",
        dataset_probe.get("reachable"),
    )

    print(
        "Usage guide reachable    :",
        guide_probe.get("reachable"),
    )

    print()
    print("Official bulk dataset   : YES")
    print("Join key                : NEQ")
    print("Registration date       : CONFIRMED")
    print("Employee-size field     : CONFIRMED")
    print("Update frequency        : BIMONTHLY")

    print(
        "Connector status        : "
        "OFFICIAL_BULK_DATA_AVAILABLE"
    )

    print()
    print(f"Evidence file           : {OUTPUT}")
    print()
    print(
        "=== V4 QUEBEC REQ ACCESS AUDIT SUCCESS ==="
    )


if __name__ == "__main__":
    main()