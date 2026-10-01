from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = ROOT / "data" / "processed" / "v4" / "registry"
OUTPUT = OUTPUT_DIR / "alberta_registry_access_audit.json"

CORPORATION_SEARCH_URL = (
    "https://www.alberta.ca/find-corporation-details"
)

BUSINESS_REGISTRY_URL = (
    "https://www.alberta.ca/find-business-registry"
)

SUBSCRIBER_URL = (
    "https://www.alberta.ca/registries-online-subscribers"
)

REGISTRY_AGENT_URL = (
    "https://www.alberta.ca/lookup/find-a-registry-agent.aspx"
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
    print("=== V4 ALBERTA REGISTRY ACCESS AUDIT ===")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    corporation_probe = probe(CORPORATION_SEARCH_URL)
    business_probe = probe(BUSINESS_REGISTRY_URL)
    subscriber_probe = probe(SUBSCRIBER_URL)
    agent_probe = probe(REGISTRY_AGENT_URL)

    audit = {
        "registry_source": "ALBERTA_CORPORATE_REGISTRY",
        "jurisdiction": "Alberta",
        "registry_type": "PROVINCIAL_REGISTRY",

        "official_corporation_search_url":
            CORPORATION_SEARCH_URL,

        "official_business_registry_url":
            BUSINESS_REGISTRY_URL,

        "official_subscriber_url":
            SUBSCRIBER_URL,

        "official_registry_agent_url":
            REGISTRY_AGENT_URL,

        "registry_agent_search_available": True,

        "registry_search_paid": True,

        "registries_online_available": True,

        "unrestricted_public_bulk_api_confirmed":
            False,

        "unrestricted_public_bulk_dump_confirmed":
            False,

        "search_fields_documented": [
            "registration_date",
            "owners",
            "directors",
            "legal_addresses",
        ],

        "connector_status":
            "OFFICIAL_SEARCH_AVAILABLE_RESTRICTED_ACCESS",

        "important_notes": [
            (
                "Alberta Corporate Registry searches are "
                "provided through authorized registry agents."
            ),
            (
                "Registry agents charge a government fee "
                "and a service fee for search products."
            ),
            (
                "Certified current searches can include "
                "registration date, owners, directors and "
                "legal addresses."
            ),
            (
                "Registries Online provides direct system "
                "access to eligible subscribing businesses, "
                "subject to Alberta eligibility and usage "
                "requirements."
            ),
            (
                "No unrestricted official public bulk "
                "Corporate Registry API or bulk registry "
                "dump has been confirmed by this audit."
            ),
            (
                "Existing Calgary and Edmonton municipal "
                "business-licence collectors are separate "
                "sources and are not represented as Alberta "
                "Corporate Registry data."
            ),
        ],

        "probes": {
            "corporation_search":
                corporation_probe,

            "business_registry":
                business_probe,

            "registries_online":
                subscriber_probe,

            "registry_agent_search":
                agent_probe,
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
        "Corporation search page :",
        corporation_probe.get("reachable"),
    )

    print(
        "Business registry page  :",
        business_probe.get("reachable"),
    )

    print(
        "Registries Online page  :",
        subscriber_probe.get("reachable"),
    )

    print(
        "Registry Agent search   :",
        agent_probe.get("reachable"),
    )

    print()
    print("Registry-agent search   : YES")
    print("Search products paid    : YES")
    print("Registries Online       : YES")
    print("Confirmed public API    : NO")
    print("Confirmed bulk dump     : NO")

    print(
        "Connector status        : "
        "OFFICIAL_SEARCH_AVAILABLE_RESTRICTED_ACCESS"
    )

    print()
    print(f"Evidence file           : {OUTPUT}")
    print()
    print(
        "=== V4 ALBERTA REGISTRY ACCESS AUDIT SUCCESS ==="
    )


if __name__ == "__main__":
    main()