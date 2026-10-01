from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

V4 = ROOT / "v4"
DATA_V4 = ROOT / "data" / "processed" / "v4"

OUTPUT_DIR = DATA_V4 / "handover"
OUTPUT_JSON = OUTPUT_DIR / "submission_manifest.json"
OUTPUT_MD = OUTPUT_DIR / "SUBMISSION_MANIFEST.md"

MAX_RECOMMENDED_SIZE = 25 * 1024 * 1024  # 25 MB


# Files/directories that must never be recommended for submission.
SENSITIVE_NAMES = {
    ".env",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
}

SENSITIVE_SUFFIXES = {
    ".pem",
    ".key",
    ".pfx",
    ".p12",
}

# Small evidence artifacts useful for review/handover.
EVIDENCE_FILES = [
    DATA_V4 / "audit" / "karan_six_point_validation.json",
    DATA_V4 / "handover" / "karan_v4_handover_summary.json",
    DATA_V4 / "handover" / "karan_v4_handover_summary.md",
    DATA_V4 / "new_businesses" / "quebec_new_business_detection.json",
    DATA_V4 / "enrichment" / "decision_maker_sample.csv",
    DATA_V4 / "enrichment" / "decision_maker_sample_evidence.json",
    DATA_V4 / "enrichment" / "decision_maker_discovery_audit.json",
    DATA_V4 / "provenance" / "field_provenance_metadata.json",
    DATA_V4 / "website_quality" / "website_cleanup_audit.json",
]

DOCUMENTATION_FILES = [
    ROOT / "README.md",
    V4 / "V4_HANDOVER.md",
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def size_bytes(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    return path.stat().st_size


def human_size(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)

    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024

    return f"{value} B"


def is_sensitive(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}

    if any(name.lower() in parts for name in SENSITIVE_NAMES):
        return True

    if path.suffix.lower() in SENSITIVE_SUFFIXES:
        return True

    name = path.name.lower()

    sensitive_tokens = [
        "credential",
        "credentials",
        "secret",
        "password",
        "private_key",
        "service_account",
    ]

    return any(token in name for token in sensitive_tokens)


def collect_v4_scripts() -> list[Path]:
    if not V4.exists():
        return []

    return sorted(
        path
        for path in V4.rglob("*.py")
        if path.is_file() and not is_sensitive(path)
    )


def file_record(path: Path, category: str) -> dict:
    size = size_bytes(path)

    return {
        "category": category,
        "path": rel(path),
        "exists": path.exists(),
        "size_bytes": size,
        "size_human": human_size(size),
        "recommended": (
            path.exists()
            and path.is_file()
            and not is_sensitive(path)
            and size <= MAX_RECOMMENDED_SIZE
        ),
    }


def main() -> None:
    print("=== V4 SUBMISSION MANIFEST BUILD ===")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []

    # -------------------------------------------------
    # Source code
    # -------------------------------------------------

    for path in collect_v4_scripts():
        records.append(
            file_record(path, "V4_SOURCE_CODE")
        )

    # -------------------------------------------------
    # Documentation
    # -------------------------------------------------

    for path in DOCUMENTATION_FILES:
        records.append(
            file_record(path, "DOCUMENTATION")
        )

    # -------------------------------------------------
    # Small evidence
    # -------------------------------------------------

    for path in EVIDENCE_FILES:
        records.append(
            file_record(path, "VALIDATION_EVIDENCE")
        )

    # Remove duplicate paths while preserving first category.
    unique = {}
    for item in records:
        unique.setdefault(item["path"], item)

    records = list(unique.values())

    included = [
        item
        for item in records
        if item["recommended"]
    ]

    missing = [
        item
        for item in records
        if not item["exists"]
    ]

    oversized = [
        item
        for item in records
        if (
            item["exists"]
            and item["size_bytes"] > MAX_RECOMMENDED_SIZE
        )
    ]

    # -------------------------------------------------
    # Scan project for obvious sensitive files.
    # Do not print contents.
    # -------------------------------------------------

    sensitive_found = []

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        if is_sensitive(path):
            sensitive_found.append(
                {
                    "path": rel(path),
                    "size_bytes": size_bytes(path),
                    "size_human": human_size(size_bytes(path)),
                }
            )

    # -------------------------------------------------
    # Identify very large data files separately.
    # -------------------------------------------------

    large_data_files = []

    data_root = ROOT / "data"

    if data_root.exists():
        for path in data_root.rglob("*"):
            if not path.is_file():
                continue

            size = size_bytes(path)

            if size > MAX_RECOMMENDED_SIZE:
                large_data_files.append(
                    {
                        "path": rel(path),
                        "size_bytes": size,
                        "size_human": human_size(size),
                    }
                )

    large_data_files.sort(
        key=lambda x: x["size_bytes"],
        reverse=True,
    )

    sensitive_found.sort(
        key=lambda x: x["path"].lower()
    )

    total_submission_bytes = sum(
        item["size_bytes"]
        for item in included
    )

    manifest = {
        "built_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "project_root": str(ROOT),
        "purpose": (
            "Read-only submission manifest for V4 handover. "
            "No project files were deleted, moved or modified."
        ),
        "submission_policy": {
            "include": [
                "V4 Python source code",
                "README / V4 handover documentation",
                "small validation and audit evidence",
            ],
            "exclude": [
                ".env and credentials",
                ".venv and local environment files",
                "__pycache__ and development caches",
                "raw source dumps",
                "large generated CSV/Parquet datasets unless explicitly requested",
            ],
            "recommended_max_individual_file_bytes":
                MAX_RECOMMENDED_SIZE,
        },
        "recommended_files": included,
        "missing_expected_files": missing,
        "oversized_recommended_candidates": oversized,
        "sensitive_files_detected": sensitive_found,
        "large_data_files_detected": large_data_files,
        "recommended_file_count": len(included),
        "recommended_total_bytes": total_submission_bytes,
        "recommended_total_human": human_size(
            total_submission_bytes
        ),
    }

    OUTPUT_JSON.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    lines = []

    lines.append("# V4 Submission Manifest")
    lines.append("")
    lines.append(
        "This manifest identifies the recommended handover "
        "files without deleting, moving, or modifying the "
        "existing project."
    )
    lines.append("")

    lines.append("## Recommended Submission")
    lines.append("")
    lines.append(
        f"Files: **{len(included)}**"
    )
    lines.append(
        f"Approximate size: **{human_size(total_submission_bytes)}**"
    )
    lines.append("")

    for item in included:
        lines.append(
            f"- `{item['path']}` "
            f"— {item['category']} "
            f"({item['size_human']})"
        )

    lines.append("")
    lines.append("## Explicit Exclusions")
    lines.append("")
    lines.append("- `.env` and credentials")
    lines.append("- `.venv` / local Python environment")
    lines.append("- `__pycache__` and development caches")
    lines.append("- Raw source dumps")
    lines.append(
        "- Large generated CSV/Parquet datasets unless "
        "the reviewer explicitly requests them"
    )
    lines.append("")

    if missing:
        lines.append("## Missing Expected Files")
        lines.append("")

        for item in missing:
            lines.append(
                f"- `{item['path']}`"
            )

        lines.append("")

    if sensitive_found:
        lines.append("## Sensitive Files Detected")
        lines.append("")
        lines.append(
            "**Do not include these automatically in a submission.**"
        )
        lines.append("")

        for item in sensitive_found:
            lines.append(
                f"- `{item['path']}` "
                f"({item['size_human']})"
            )

        lines.append("")

    if large_data_files:
        lines.append("## Large Data Files")
        lines.append("")
        lines.append(
            "These are excluded from the lightweight handover "
            "unless specifically requested."
        )
        lines.append("")

        for item in large_data_files[:30]:
            lines.append(
                f"- `{item['path']}` "
                f"({item['size_human']})"
            )

        if len(large_data_files) > 30:
            lines.append(
                f"- ... plus {len(large_data_files) - 30} "
                "additional large files."
            )

        lines.append("")

    lines.append("## Final Validation")
    lines.append("")
    lines.append(
        "Run the lightweight V4 demo from the project root:"
    )
    lines.append("")
    lines.append(
        "`.\\.venv\\Scripts\\python.exe "
        ".\\v4\\audit\\run_v4_demo.py`"
    )
    lines.append("")
    lines.append(
        "Expected final status: **V4 DEMO STATUS: PASS / "
        "Requirements: 6/6**."
    )
    lines.append("")

    OUTPUT_MD.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(
        "Recommended files       :",
        len(included),
    )

    print(
        "Recommended package size:",
        human_size(total_submission_bytes),
    )

    print(
        "Sensitive files detected:",
        len(sensitive_found),
    )

    print(
        "Large data files        :",
        len(large_data_files),
    )

    print(
        "Missing expected files  :",
        len(missing),
    )

    print()
    print("JSON manifest :", OUTPUT_JSON)
    print("Markdown      :", OUTPUT_MD)
    print()
    print(
        "NOTE: No files were deleted, moved or copied."
    )
    print()
    print(
        "=== V4 SUBMISSION MANIFEST SUCCESS ==="
    )


if __name__ == "__main__":
    main()