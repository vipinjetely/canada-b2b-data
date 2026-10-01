from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "data" / "processed" / "v4" / "registry"
OUTPUT = OUTPUT_DIR / "ontario_registry_access_audit.json"

OBR_INFO_URL = (
    "https://www.ontario.ca/page/"
    "ontario-business-registry"
)

OBR_ACCOUNT_URL = (
    "https://www.ontario.ca/page/"
    "ontario-business-account"
)

PARTNER_PORTAL_URL = (
    "https://www.ontario.ca/page/"
    "ontario-business-registry-partner-portal"
)

OPEN_DATA_URL = (
    "https://data.ontario.ca/dataset/"
    "ontario-business-registry-partner-portal"
)


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
            "reachable": True,
            "http_status": response.status_code,
            "final_url": response.url,
            "content_type":
                response.headers.get("Content-Type"),
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
    print("=== V4 ONTARIO REGISTRY ACCESS AUDIT ===")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    obr_probe = probe(OBR_INFO_URL)
    account_probe = probe(OBR_ACCOUNT_URL)
    partner_probe = probe(PARTNER_PORTAL_URL)
    open_data_probe = probe(OPEN_DATA_URL)

    audit = {
        "registry_source": "ONTARIO_BUSINESS_REGISTRY",
        "jurisdiction": "Ontario",
        "registry_type": "PROVINCIAL_REGISTRY",

        "official_registry_information_url":
            OBR_INFO_URL,

        "official_business_account_url":
            OBR_ACCOUNT_URL,

        "official_partner_portal_url":
            PARTNER_PORTAL_URL,

        "ontario_open_data_reference":
            OPEN_DATA_URL,

        "public_basic_search_available": True,

        "detailed_search_products_paid": True,

        "unrestricted_bulk_registry_api_confirmed":
            False,

        "unrestricted_bulk_registry_dump_confirmed":
            False,

        "connector_status":
            "PUBLIC_SEARCH_AVAILABLE_NO_CONFIRMED_BULK_API",

        "important_notes": [
            (
                "Ontario Business Registry provides a "
                "public search for basic business "
                "information."
            ),
            (
                "Detailed registry search products may "
                "require payment."
            ),
            (
                "Business profile management uses "
                "Ontario.ca Login / Ontario Business "
                "Account and, where applicable, a "
                "company key."
            ),
            (
                "The Ontario Open Data dataset named "
                "'Ontario Business Registry Partner "
                "Portal' is a list of intermediaries "
                "with Partner Portal access. It is NOT "
                "a bulk dataset of Ontario registered "
                "businesses."
            ),
            (
                "No unrestricted official bulk OBR "
                "corporate-registry API or registry dump "
                "has been confirmed by this audit."
            ),
        ],

        "probes": {
            "obr_information": obr_probe,
            "business_account": account_probe,
            "partner_portal": partner_probe,
            "open_data_reference": open_data_probe,
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
        "OBR information reachable :",
        obr_probe.get("reachable"),
    )

    print(
        "Business account reachable:",
        account_probe.get("reachable"),
    )

    print(
        "Partner Portal reachable  :",
        partner_probe.get("reachable"),
    )

    print(
        "Open Data page reachable  :",
        open_data_probe.get("reachable"),
    )

    print()
    print("Public basic search      : YES")
    print("Confirmed bulk API       : NO")
    print("Confirmed bulk dump      : NO")

    print(
        "Connector status         : "
        "PUBLIC_SEARCH_AVAILABLE_NO_CONFIRMED_BULK_API"
    )

    print()
    print(f"Evidence file            : {OUTPUT}")
    print()
    print(
        "=== V4 ONTARIO REGISTRY ACCESS AUDIT SUCCESS ==="
    )


if __name__ == "__main__":
    main()