from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "data" / "processed" / "v4" / "registry"
OUTPUT = OUTPUT_DIR / "bc_registry_access_audit.json"

DOCUMENTATION_URL = (
    "https://developer.api.bcregistry.gov.bc.ca/"
    "en-CA/products/rs/overview/"
)

PRODUCTION_BASE_URL = "https://api.connect.gov.bc.ca"
SANDBOX_BASE_URL = "https://sandbox.api.connect.gov.bc.ca"

BULK_SEARCH_PATH = "/registry-search/api/v2/search/businesses/bulk"


def probe(url: str) -> dict:
    checked_at = datetime.now(timezone.utc).isoformat()

    try:
        response = requests.get(
            url,
            timeout=(10, 30),
            allow_redirects=True,
            headers={
                "User-Agent":
                    "Canada-B2B-Data-Automation/4.0"
            },
        )

        return {
            "url": url,
            "checked_at_utc": checked_at,
            "http_status": response.status_code,
            "final_url": response.url,
            "content_type":
                response.headers.get("Content-Type"),
            "reachable": True,
        }

    except requests.RequestException as exc:
        return {
            "url": url,
            "checked_at_utc": checked_at,
            "reachable": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def main() -> None:
    print("=== V4 BC REGISTRY ACCESS AUDIT ===")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    documentation_probe = probe(DOCUMENTATION_URL)

    production_probe = probe(
        PRODUCTION_BASE_URL + BULK_SEARCH_PATH
    )

    sandbox_probe = probe(
        SANDBOX_BASE_URL + BULK_SEARCH_PATH
    )

    audit = {
        "registry_source": "BC_REGISTRIES",
        "jurisdiction": "British Columbia",
        "registry_type": "PROVINCIAL_REGISTRY",

        "official_documentation_url":
            DOCUMENTATION_URL,

        "production_base_url":
            PRODUCTION_BASE_URL,

        "sandbox_base_url":
            SANDBOX_BASE_URL,

        "bulk_business_search_path":
            BULK_SEARCH_PATH,

        "authentication_required": True,

        "required_credentials": [
            "BC Registries issued API key",
            "BC Registries Account ID",
        ],

        "connector_status":
            "BLOCKED_PENDING_OFFICIAL_CREDENTIALS",

        "important_note": (
            "The official BC Registry Search API exists, "
            "including a bulk business-search endpoint. "
            "Production requests require a BC Registries "
            "issued API key and Account ID. This audit does "
            "not claim registry data access without those "
            "credentials."
        ),

        "probes": {
            "documentation": documentation_probe,
            "production_bulk_endpoint":
                production_probe,
            "sandbox_bulk_endpoint":
                sandbox_probe,
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
        "Documentation reachable :",
        documentation_probe.get("reachable"),
    )

    print(
        "Production HTTP status  :",
        production_probe.get("http_status"),
    )

    print(
        "Sandbox HTTP status     :",
        sandbox_probe.get("http_status"),
    )

    print()
    print(
        "Authentication required : YES "
        "(API key + Account ID)"
    )

    print(
        "Connector status        : "
        "BLOCKED_PENDING_OFFICIAL_CREDENTIALS"
    )

    print()
    print(f"Evidence file           : {OUTPUT}")
    print()
    print("=== V4 BC REGISTRY ACCESS AUDIT SUCCESS ===")


if __name__ == "__main__":
    main()