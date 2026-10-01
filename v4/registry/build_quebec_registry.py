from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[2]

SOURCE_ZIP = Path(
    r"C:\Users\Hp\Desktop\Project Video Editing"
    r"\Material\JeuDonnees.zip"
)

WORK_DIR = ROOT / "data" / "raw" / "v4" / "quebec_req_extracted"

OUTPUT_DIR = ROOT / "data" / "processed" / "v4" / "registry"
OUTPUT = OUTPUT_DIR / "quebec_registry.parquet"
METADATA_OUTPUT = OUTPUT_DIR / "quebec_registry_metadata.json"

EXPECTED_FILES = {
    "Entreprise.csv",
    "Nom.csv",
    "Etablissements.csv",
    "FusionScissions.csv",
    "ContinuationsTransformations.csv",
    "DomaineValeur.csv",
}

SOURCE_KEY = "QUEBEC_REQ"

SOURCE_PAGE = (
    "https://www.donneesquebec.ca/recherche/dataset/"
    "registre-des-entreprises"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def inspect_archive() -> None:
    if not SOURCE_ZIP.exists():
        raise FileNotFoundError(
            f"Quebec REQ ZIP not found: {SOURCE_ZIP}"
        )

    if not zipfile.is_zipfile(SOURCE_ZIP):
        raise RuntimeError(
            f"Source is not a valid ZIP: {SOURCE_ZIP}"
        )

    with zipfile.ZipFile(SOURCE_ZIP, "r") as archive:
        csv_names = {
            Path(name).name
            for name in archive.namelist()
            if name.lower().endswith(".csv")
        }

    missing = EXPECTED_FILES - csv_names
    unexpected = csv_names - EXPECTED_FILES

    if missing:
        raise RuntimeError(
            "Quebec archive is missing expected files: "
            + ", ".join(sorted(missing))
        )

    if unexpected:
        print(
            "WARNING - unexpected CSV files present: "
            + ", ".join(sorted(unexpected))
        )


def extract_required_files() -> None:
    print("Extracting required Quebec REQ CSV files...")

    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)

    WORK_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with zipfile.ZipFile(SOURCE_ZIP, "r") as archive:
        members = {
            Path(name).name: name
            for name in archive.namelist()
            if name.lower().endswith(".csv")
        }

        for filename in sorted(EXPECTED_FILES):
            member = members[filename]
            destination = WORK_DIR / filename

            print(f"  Extracting {filename}...")

            with archive.open(member) as source:
                with destination.open("wb") as target:
                    shutil.copyfileobj(
                        source,
                        target,
                        length=1024 * 1024,
                    )

    print("Extraction complete.")
    print()


def detect_delimiter(path: Path) -> str:
    with path.open(
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline="",
    ) as handle:
        sample = handle.read(8192)

    try:
        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=",;|\t",
        )
        return dialect.delimiter
    except csv.Error:
        return ","


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def sql_literal(value: str) -> str:
    return value.replace("'", "''")


def create_csv_view(
    con: duckdb.DuckDBPyConnection,
    view_name: str,
    path: Path,
) -> None:
    delimiter = detect_delimiter(path)

    print(
        f"{path.name}: detected delimiter "
        f"{delimiter!r}"
    )

    con.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW {view_name} AS
        SELECT *
        FROM read_csv(
            '{sql_path(path)}',
            header = true,
            all_varchar = true,
            delim = '{sql_literal(delimiter)}',
            quote = '"',
            escape = '"',
            ignore_errors = false
        )
        """
    )


def main() -> None:
    print("=== V4 QUEBEC REGISTRY BUILD ===")
    print()

    inspect_archive()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    extract_required_files()

    source_sha256 = sha256_file(SOURCE_ZIP)
    verified_at = datetime.now(
        timezone.utc
    ).isoformat()

    entreprise = WORK_DIR / "Entreprise.csv"
    nom = WORK_DIR / "Nom.csv"
    domaines = WORK_DIR / "DomaineValeur.csv"

    con = duckdb.connect()

    try:
        # --------------------------------------------------
        # Load the three files required for the standardized
        # enterprise-level registry layer.
        # --------------------------------------------------

        create_csv_view(
            con,
            "entreprise_raw",
            entreprise,
        )

        create_csv_view(
            con,
            "nom_raw",
            nom,
        )

        create_csv_view(
            con,
            "domain_raw",
            domaines,
        )

        # --------------------------------------------------
        # Raw validation
        # --------------------------------------------------

        enterprise_count = con.execute(
            """
            SELECT COUNT(*)
            FROM entreprise_raw
            """
        ).fetchone()[0]

        blank_neq = con.execute(
            """
            SELECT COUNT(*)
            FROM entreprise_raw
            WHERE NULLIF(TRIM(NEQ), '') IS NULL
            """
        ).fetchone()[0]

        duplicate_neq_groups = con.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT TRIM(NEQ)
                FROM entreprise_raw
                WHERE NULLIF(TRIM(NEQ), '') IS NOT NULL
                GROUP BY TRIM(NEQ)
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

        print()
        print("=== RAW VALIDATION ===")
        print(
            f"Entreprise records     : "
            f"{enterprise_count:,}"
        )
        print(
            f"Blank NEQ              : "
            f"{blank_neq:,}"
        )
        print(
            f"Duplicate NEQ groups   : "
            f"{duplicate_neq_groups:,}"
        )

        if enterprise_count == 0:
            raise RuntimeError(
                "Entreprise.csv contains zero records."
            )

        if blank_neq != 0:
            raise RuntimeError(
                "Blank NEQ values detected."
            )

        if duplicate_neq_groups != 0:
            raise RuntimeError(
                "Duplicate NEQ values detected in "
                "Entreprise.csv."
            )

        # --------------------------------------------------
        # Domain lookup views.
        #
        # IMPORTANT:
        # Match BOTH domain type and code.
        # A code such as A or O can exist in several
        # unrelated domains.
        # --------------------------------------------------

        con.execute(
            """
            CREATE OR REPLACE TEMP VIEW employee_domain AS

            SELECT
                TRIM(COD_DOM_VAL) AS code,
                NULLIF(TRIM(VAL_DOM_FRAN), '') AS description

            FROM domain_raw

            WHERE UPPER(TRIM(TYP_DOM_VAL))
                = 'INTVAL_EMPLO_QUE'
            """
        )

        con.execute(
            """
            CREATE OR REPLACE TEMP VIEW status_domain AS

            SELECT
                TRIM(COD_DOM_VAL) AS code,
                NULLIF(TRIM(VAL_DOM_FRAN), '') AS description

            FROM domain_raw

            WHERE UPPER(TRIM(TYP_DOM_VAL))
                = 'STAT_IMMAT'
            """
        )

        con.execute(
            """
            CREATE OR REPLACE TEMP VIEW legal_form_domain AS

            SELECT
                TRIM(COD_DOM_VAL) AS code,
                NULLIF(TRIM(VAL_DOM_FRAN), '') AS description

            FROM domain_raw

            WHERE UPPER(TRIM(TYP_DOM_VAL))
                = 'FORM_JURI'
            """
        )

        con.execute(
            """
            CREATE OR REPLACE TEMP VIEW regime_domain AS

            SELECT
                TRIM(COD_DOM_VAL) AS code,
                NULLIF(TRIM(VAL_DOM_FRAN), '') AS description

            FROM domain_raw

            WHERE UPPER(TRIM(TYP_DOM_VAL))
                = 'REGIM_JURI'
            """
        )

        con.execute(
            """
            CREATE OR REPLACE TEMP VIEW activity_domain AS

            SELECT
                TRIM(COD_DOM_VAL) AS code,
                NULLIF(TRIM(VAL_DOM_FRAN), '') AS description

            FROM domain_raw

            WHERE UPPER(TRIM(TYP_DOM_VAL))
                = 'ACT_ECON'
            """
        )

        # --------------------------------------------------
        # Choose one current legal/business name per NEQ.
        #
        # We do NOT blindly take the first Nom.csv row.
        # Prefer a current name (no end date), then the most
        # recent start date.
        # --------------------------------------------------

        con.execute(
            """
            CREATE OR REPLACE TEMP VIEW selected_name AS

            SELECT
                neq,
                business_name,
                name_type_code,
                name_status_code,
                name_start_date,
                name_end_date

            FROM (
                SELECT
                    TRIM(NEQ) AS neq,

                    NULLIF(
                        TRIM(NOM_ASSUJ),
                        ''
                    ) AS business_name,

                    NULLIF(
                        TRIM(TYP_NOM_ASSUJ),
                        ''
                    ) AS name_type_code,

                    NULLIF(
                        TRIM(STAT_NOM),
                        ''
                    ) AS name_status_code,

                    TRY_CAST(
                        NULLIF(
                            TRIM(DAT_INIT_NOM_ASSUJ),
                            ''
                        )
                        AS DATE
                    ) AS name_start_date,

                    TRY_CAST(
                        NULLIF(
                            TRIM(DAT_FIN_NOM_ASSUJ),
                            ''
                        )
                        AS DATE
                    ) AS name_end_date,

                    ROW_NUMBER() OVER (
                        PARTITION BY TRIM(NEQ)

                        ORDER BY
                            CASE
                                WHEN NULLIF(
                                    TRIM(DAT_FIN_NOM_ASSUJ),
                                    ''
                                ) IS NULL
                                THEN 0
                                ELSE 1
                            END,

                            TRY_CAST(
                                NULLIF(
                                    TRIM(DAT_INIT_NOM_ASSUJ),
                                    ''
                                )
                                AS DATE
                            ) DESC NULLS LAST,

                            NULLIF(
                                TRIM(NOM_ASSUJ),
                                ''
                            )
                    ) AS rn

                FROM nom_raw

                WHERE NULLIF(
                    TRIM(NEQ),
                    ''
                ) IS NOT NULL

                AND NULLIF(
                    TRIM(NOM_ASSUJ),
                    ''
                ) IS NOT NULL
            )

            WHERE rn = 1
            """
        )

        # --------------------------------------------------
        # Standardized registry output
        # --------------------------------------------------

        if OUTPUT.exists():
            OUTPUT.unlink()

        output_path = sql_path(OUTPUT)

        con.execute(
            f"""
            COPY (

                SELECT
                    '{SOURCE_KEY}'
                        AS registry_source,

                    TRIM(e.NEQ)
                        AS registry_id,

                    TRIM(e.NEQ)
                        AS neq,

                    n.business_name
                        AS legal_business_name,

                    n.name_type_code,

                    n.name_status_code,

                    n.name_start_date,

                    n.name_end_date,

                    TRY_CAST(
                        NULLIF(
                            TRIM(e.DAT_IMMAT),
                            ''
                        )
                        AS DATE
                    )
                        AS registration_date,

                    TRY_CAST(
                        NULLIF(
                            TRIM(e.DAT_CONSTI),
                            ''
                        )
                        AS DATE
                    )
                        AS constitution_date,

                    NULLIF(
                        TRIM(e.COD_STAT_IMMAT),
                        ''
                    )
                        AS registration_status_code,

                    sd.description
                        AS registration_status,

                    CASE
                        WHEN TRIM(e.COD_STAT_IMMAT) = 'IM'
                            THEN TRUE
                        WHEN NULLIF(
                            TRIM(e.COD_STAT_IMMAT),
                            ''
                        ) IS NULL
                            THEN NULL
                        ELSE FALSE
                    END
                        AS is_currently_registered,

                    NULLIF(
                        TRIM(e.COD_FORME_JURI),
                        ''
                    )
                        AS legal_form_code,

                    lf.description
                        AS legal_form,

                    NULLIF(
                        TRIM(e.COD_REGIM_JURI),
                        ''
                    )
                        AS governing_regime_code,

                    rg.description
                        AS governing_regime,

                    NULLIF(
                        TRIM(e.COD_REGIM_JURI_CONSTI),
                        ''
                    )
                        AS constitution_regime_code,

                    NULLIF(
                        TRIM(e.COD_INTVAL_EMPLO_QUE),
                        ''
                    )
                        AS employee_size_code,

                    ed.description
                        AS employee_size_bucket,

                    CASE
                        WHEN NULLIF(
                            TRIM(e.COD_INTVAL_EMPLO_QUE),
                            ''
                        ) IS NULL
                            THEN NULL

                        WHEN TRIM(e.COD_INTVAL_EMPLO_QUE)
                            = 'N'
                            THEN 'UNDECLARED'

                        ELSE 'CONFIRMED_REGISTRY_RANGE'
                    END
                        AS employee_count_type,

                    NULLIF(
                        TRIM(e.COD_ACT_ECON_CAE),
                        ''
                    )
                        AS primary_activity_code,

                    ad1.description
                        AS primary_activity,

                    NULLIF(
                        TRIM(e.DESC_ACT_ECON_ASSUJ),
                        ''
                    )
                        AS declared_primary_activity,

                    NULLIF(
                        TRIM(e.COD_ACT_ECON_CAE2),
                        ''
                    )
                        AS secondary_activity_code,

                    ad2.description
                        AS secondary_activity,

                    NULLIF(
                        TRIM(e.DESC_ACT_ECON_ASSUJ2),
                        ''
                    )
                        AS declared_secondary_activity,

                    NULLIF(
                        TRIM(e.NOM_LOCLT_CONSTI),
                        ''
                    )
                        AS constitution_locality,

                    NULLIF(
                        TRIM(e.ADR_DOMCL_LIGN1_ADR),
                        ''
                    )
                        AS registered_address_line_1,

                    NULLIF(
                        TRIM(e.ADR_DOMCL_LIGN2_ADR),
                        ''
                    )
                        AS registered_address_line_2,

                    NULLIF(
                        TRIM(e.ADR_DOMCL_LIGN3_ADR),
                        ''
                    )
                        AS registered_address_line_3,

                    NULLIF(
                        TRIM(e.ADR_DOMCL_LIGN4_ADR),
                        ''
                    )
                        AS registered_address_line_4,

                    CASE
                        WHEN NULLIF(
                            TRIM(e.IND_FAIL),
                            ''
                        ) IS NULL
                            THEN NULL
                        ELSE TRIM(e.IND_FAIL)
                    END
                        AS bankruptcy_indicator,

                    CASE
                        WHEN NULLIF(
                            TRIM(e.DAT_IMMAT),
                            ''
                        ) IS NULL
                            THEN FALSE
                        ELSE TRUE
                    END
                        AS registration_date_verified,

                    CASE
                        WHEN NULLIF(
                            TRIM(e.COD_INTVAL_EMPLO_QUE),
                            ''
                        ) IS NULL
                            THEN FALSE
                        WHEN TRIM(e.COD_INTVAL_EMPLO_QUE)
                            = 'N'
                            THEN FALSE
                        ELSE TRUE
                    END
                        AS employee_size_verified,

                    '{sql_literal(SOURCE_PAGE)}'
                        AS source_url,

                    '{sql_literal(source_sha256)}'
                        AS source_sha256,

                    '{sql_literal(verified_at)}'
                        AS last_verified_at,

                    'OFFICIAL_PROVINCIAL_REGISTRY'
                        AS evidence_type

                FROM entreprise_raw e

                LEFT JOIN selected_name n
                    ON TRIM(e.NEQ) = n.neq

                LEFT JOIN status_domain sd
                    ON TRIM(e.COD_STAT_IMMAT)
                        = sd.code

                LEFT JOIN legal_form_domain lf
                    ON TRIM(e.COD_FORME_JURI)
                        = lf.code

                LEFT JOIN regime_domain rg
                    ON TRIM(e.COD_REGIM_JURI)
                        = rg.code

                LEFT JOIN employee_domain ed
                    ON TRIM(e.COD_INTVAL_EMPLO_QUE)
                        = ed.code

                LEFT JOIN activity_domain ad1
                    ON TRIM(e.COD_ACT_ECON_CAE)
                        = ad1.code

                LEFT JOIN activity_domain ad2
                    ON TRIM(e.COD_ACT_ECON_CAE2)
                        = ad2.code
            )

            TO '{output_path}'
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )

        # --------------------------------------------------
        # Output validation
        # --------------------------------------------------

        stats = con.execute(
            """
            SELECT
                COUNT(*) AS total,

                COUNT(*) FILTER (
                    WHERE legal_business_name IS NOT NULL
                ) AS names,

                COUNT(*) FILTER (
                    WHERE registration_date IS NOT NULL
                ) AS registration_dates,

                COUNT(*) FILTER (
                    WHERE constitution_date IS NOT NULL
                ) AS constitution_dates,

                COUNT(*) FILTER (
                    WHERE registration_status IS NOT NULL
                ) AS statuses,

                COUNT(*) FILTER (
                    WHERE is_currently_registered = TRUE
                ) AS currently_registered,

                COUNT(*) FILTER (
                    WHERE employee_size_verified = TRUE
                ) AS employee_sizes,

                COUNT(*) FILTER (
                    WHERE primary_activity IS NOT NULL
                ) AS activities,

                COUNT(*) FILTER (
                    WHERE legal_form IS NOT NULL
                ) AS legal_forms,

                COUNT(*) FILTER (
                    WHERE source_url IS NOT NULL
                ) AS source_rows,

                COUNT(*) FILTER (
                    WHERE last_verified_at IS NOT NULL
                ) AS verified_rows

            FROM read_parquet(?)
            """,
            [str(OUTPUT)],
        ).fetchone()

        output_duplicates = con.execute(
            """
            SELECT COUNT(*)

            FROM (
                SELECT registry_id

                FROM read_parquet(?)

                GROUP BY registry_id

                HAVING COUNT(*) > 1
            )
            """,
            [str(OUTPUT)],
        ).fetchone()[0]

        # --------------------------------------------------
        # Employee-size distribution
        # --------------------------------------------------

        employee_distribution = con.execute(
            """
            SELECT
                employee_size_code,
                employee_size_bucket,
                employee_count_type,
                COUNT(*) AS records

            FROM read_parquet(?)

            GROUP BY
                employee_size_code,
                employee_size_bucket,
                employee_count_type

            ORDER BY records DESC
            """,
            [str(OUTPUT)],
        ).fetchall()

    finally:
        con.close()

    # ------------------------------------------------------
    # Integrity gates
    # ------------------------------------------------------

    if stats[0] != enterprise_count:
        raise RuntimeError(
            "Output row count mismatch. "
            f"Source={enterprise_count:,}, "
            f"Output={stats[0]:,}"
        )

    if output_duplicates != 0:
        raise RuntimeError(
            "Duplicate NEQ values detected in output."
        )

    if stats[9] != stats[0]:
        raise RuntimeError(
            "Some records are missing source provenance."
        )

    if stats[10] != stats[0]:
        raise RuntimeError(
            "Some records are missing verification timestamp."
        )

    # ------------------------------------------------------
    # Metadata / evidence
    # ------------------------------------------------------

    metadata = {
        "registry_source": SOURCE_KEY,
        "jurisdiction": "Quebec",
        "registry_type": "PROVINCIAL_REGISTRY",

        "source_archive": str(SOURCE_ZIP),
        "source_sha256": source_sha256,
        "source_url": SOURCE_PAGE,

        "built_at_utc": verified_at,

        "source_enterprise_records":
            enterprise_count,

        "output_records":
            stats[0],

        "legal_business_names":
            stats[1],

        "registration_dates":
            stats[2],

        "constitution_dates":
            stats[3],

        "registration_statuses":
            stats[4],

        "currently_registered":
            stats[5],

        "verified_employee_size_ranges":
            stats[6],

        "mapped_primary_activities":
            stats[7],

        "mapped_legal_forms":
            stats[8],

        "duplicate_output_neq":
            output_duplicates,

        "employee_distribution": [
            {
                "code": row[0],
                "bucket": row[1],
                "type": row[2],
                "records": row[3],
            }
            for row in employee_distribution
        ],

        "evidence_type":
            "OFFICIAL_PROVINCIAL_REGISTRY",
    }

    METADATA_OUTPUT.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ------------------------------------------------------
    # Report
    # ------------------------------------------------------

    print()
    print("=== QUEBEC REGISTRY COVERAGE ===")
    print()

    print(f"Registry records        : {stats[0]:,}")
    print(f"Legal business names    : {stats[1]:,}")
    print(f"Registration dates      : {stats[2]:,}")
    print(f"Constitution dates      : {stats[3]:,}")
    print(f"Registration statuses   : {stats[4]:,}")
    print(f"Currently registered    : {stats[5]:,}")
    print(f"Verified employee ranges: {stats[6]:,}")
    print(f"Mapped activities       : {stats[7]:,}")
    print(f"Mapped legal forms      : {stats[8]:,}")
    print(f"Duplicate output NEQs   : {output_duplicates:,}")

    print()
    print("=== EMPLOYEE SIZE DISTRIBUTION ===")

    for (
        code,
        bucket,
        count_type,
        records,
    ) in employee_distribution:
        print(
            f"{code!r:>6} | "
            f"{str(bucket):<30} | "
            f"{str(count_type):<25} | "
            f"{records:,}"
        )

    print()
    print(f"Parquet  : {OUTPUT}")
    print(f"Metadata : {METADATA_OUTPUT}")
    print()
    print("=== V4 QUEBEC REGISTRY SUCCESS ===")


if __name__ == "__main__":
    main()