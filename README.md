# Canada B2B Business Data Automation System

A production-oriented data pipeline for collecting, normalizing, resolving, enriching, storing, searching, and reviewing Canadian B2B business data from legitimate public and government sources.

V2 focuses on three principles:

- current source data,
- conservative entity resolution,
- traceable source provenance.

The system does not manufacture missing business information or inflate coverage by treating duplicate licence/category rows as separate businesses.

---

## V2 Current Status

The V2 database currently contains:

- **849,849 canonical business entities**
- **948,765 source provenance records**
- **6 active source jurisdictions**
- **0 orphan provenance records**
- **0 duplicate Federal Corporation IDs**
- **0 duplicate Provincial Registry IDs**
- **0 failed records across the six recorded source loads**

The current source collection cycle was completed on **25 September 2026**.

For detailed coverage and freshness information, see:

`V2_COVERAGE_FRESHNESS_REPORT.md`

---

## Architecture

```text
Public / Government Data Sources
            |
            v
       Collectors
            |
            v
       Raw Source Data
            |
            v
       Normalizers
            |
            v
  Source-Specific Records
            |
            v
 Entity Resolution / Deduplication
            |
       +----+----+
       |         |
       v         v
 Existing      New Local
 Canonical     Canonical
 Entity        Entity
       |         |
       +----+----+
            |
            v
       PostgreSQL
            |
       +----+----+
       |         |
       v         v
   Provenance   Streamlit
   / History    Dashboard
```

The database separates canonical business entities from source records so that multiple licences or public-source records can resolve to one business without losing their original provenance.

---

## Tech Stack

- Python 3
- PostgreSQL
- Docker / Docker Compose
- pandas
- psycopg
- Streamlit
- FastAPI
- Uvicorn
- n8n
- pytest

---

## Project Structure

```text
collectors/        Public/government source collectors
normalizers/       Source-specific normalization
deduplication/     Conservative entity resolution
enrichment/        Supplemental enrichment logic
database/          PostgreSQL schemas and loaders
dashboard/         Streamlit dashboard
tests/             Data-quality/database tests
logs/              Runtime logs
data/              Local raw/processed datasets (Git ignored)

run_pipeline.py
pipeline_api.py
docker-compose.yml
requirements.txt
.env.example
V2_COVERAGE_FRESHNESS_REPORT.md
```

---

## V2 Data Sources

### 1. Corporations Canada

Federal active corporation data provides the primary national legal-entity foundation.

Key fields include:

- Federal Corporation Number
- Business Number
- Legal name
- Status
- Incorporation/filing information
- Registered address
- Province/territory
- Postal code

Current canonical Federal entities:

**645,005**

---

### 2. City of Vancouver Business Licences

Current municipal business-licence data adds local businesses and licence-level attributes.

Current canonical Vancouver entities:

**62,357**

The source also provides useful employee-count and business-category information for many records.

---

### 3. City of Toronto Business Licences and Permits

Toronto municipal licensing data contributes business identity, operating-name, category, address and available phone information.

Current canonical Toronto entities:

**33,437**

---

### 4. City of Edmonton Business Licences

Edmonton business-licence data contributes local business identity, licence/category information, address where publicly available, and recent licence activity.

Current canonical Edmonton entities:

**39,714**

---

### 5. City of Calgary Business Licences

Calgary business-licence data contributes local business identity, address and licence-category information.

Current canonical Calgary entities:

**22,766**

---

### 6. Québec RBQ Active Licences

The Régie du bâtiment du Québec active-licence dataset contributes Québec business identities and strong contact coverage.

Current canonical Québec-local entities:

**46,570**

The processed source also contains strong Federal matches that are linked through provenance rather than inserted as duplicate entities.

---

## Coverage Summary

| Registry Jurisdiction | Canonical Entities |
|---|---:|
| Federal | 645,005 |
| Vancouver, BC | 62,357 |
| Québec, QC | 46,570 |
| Edmonton, AB | 39,714 |
| Toronto, ON | 33,437 |
| Calgary, AB | 22,766 |
| **Total** | **849,849** |

These figures represent the current canonical database state.

They should not be interpreted as a claim that the system contains every business in Canada or that every record is guaranteed nationally unique across every possible external registry.

---

## Source Freshness

| Source | Upstream Source Date | Collected |
|---|---|---|
| Corporations Canada | 2026-09-25 | 2026-09-25 |
| Vancouver Business Licences | 2026-09-24 | 2026-09-25 |
| Toronto Business Licences | 2026-09-25 | 2026-09-25 |
| Edmonton Business Licences | 2026-09-23 | 2026-09-25 |
| Calgary Business Licences | Not reliably supplied upstream | 2026-09-25 |
| Québec RBQ Active Licences | 2026-09-25 | 2026-09-25 |

Source update timestamps and collection timestamps are stored separately.

If a source does not reliably provide its own update timestamp, the system does not manufacture one.

---

## Data Processing

### Collection

Each collector retrieves a specific public/government source and stores the raw data locally together with collection metadata where available.

### Normalization

Source-specific normalizers standardize fields such as:

- legal/operating name
- business identifiers
- address
- city/province
- postal code
- phone/email
- industry/category
- employee count/bucket
- status
- source identifiers
- collection timestamps

Missing fields remain missing rather than being inferred.

### Entity Resolution

Entity resolution is intentionally conservative.

Strong identifiers are preferred where available:

- Federal Corporation Number
- Québec NEQ / provincial identifier
- municipal licence/source identifiers

Cross-source matching may additionally use:

- normalized legal name
- city
- postal code
- address
- unique-name constraints

Ambiguous name-only candidates are retained for review instead of being automatically merged.

---

## PostgreSQL V2 Model

V2 uses a canonical/provenance-oriented schema.

Primary tables include:

```text
data_sources
business_entities
business_source_records
field_provenance
business_contacts
business_change_history
pipeline_runs
```

`business_entities` stores the canonical business representation.

`business_source_records` preserves the source records that support or map to those canonical entities.

This allows the system to deduplicate source records without discarding traceability.

---

## Verified Database Integrity

Current integrity validation:

```text
Canonical entities:          849,849
Source provenance records:   948,765
Orphan provenance records:         0
Duplicate Federal IDs:             0
Duplicate Provincial IDs:          0
```

This validation checks database identity and provenance integrity rather than simply comparing raw source row counts.

---

## Contact and Attribute Coverage

Available contact information varies by source.

Current examples include:

- Québec-local entities with phone: **46,564**
- Québec-local entities with email: **44,196**
- Toronto entities with phone: **12,479**
- Federal entities with phone after enrichment: **3,471**
- Federal entities with email after enrichment: **2,990**

Phone numbers, emails, websites, employee counts and other missing fields are not fabricated.

---

## Recent Activity Signals

The V2 schema supports:

```text
is_new_1d
is_new_7d
is_new_30d
```

Current database totals include:

- **624** records with a 7-day source activity signal
- **3,852** records with a 30-day source activity signal

These values are source-specific signals.

Depending on the source, the underlying date may represent licence issuance, recent licence activity or another source-defined business event. They are therefore not universally described as newly incorporated companies.

---

## Streamlit Dashboard

Start the dashboard with:

```powershell
streamlit run dashboard/app.py
```

The V2 dashboard queries `business_entities` and provides:

- total canonical entity count
- phone/email availability metrics
- jurisdiction summary
- source freshness/provenance view
- business-name search
- Federal Corporation Number search
- Business Number search
- provincial registry identifier search
- city search
- jurisdiction filtering
- status filtering
- industry/category filtering
- contact-availability filtering
- recent 7-day/30-day activity filtering
- quality/confidence fields
- CSV export

The full dataset is queried through PostgreSQL rather than loaded into the browser.

---

## Pipeline Execution History

The database records source-load execution metrics in `pipeline_runs`.

The current six recorded source loads all completed successfully with:

**0 failed records**

The execution history tracks:

- records collected
- records inserted
- records updated
- records deduplicated/linked
- failed records
- start/end timestamps
- pipeline status

---

## Local Setup

### 1. Create virtual environment

```powershell
python -m venv .venv
```

### 2. Activate on Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure environment

Copy:

```text
.env.example
```

to:

```text
.env
```

and provide the local PostgreSQL configuration.

Do not commit `.env`.

### 5. Start PostgreSQL

```powershell
docker compose up -d postgres
```

### 6. Apply database schemas

The repository contains the database schema files used by the project, including the V2 canonical/provenance schema.

Apply the required schema before the first load.

### 7. Start the dashboard

```powershell
streamlit run dashboard/app.py
```

---

## FastAPI / n8n Orchestration

The project includes the V1 FastAPI/n8n orchestration foundation.

The API can be started locally with:

```powershell
python -m uvicorn pipeline_api:app --host 0.0.0.0 --port 8000
```

Endpoints include:

```text
GET  /health
GET  /pipeline/status
POST /pipeline/run
```

The existing n8n workflow can trigger the API and monitor pipeline status until completion or failure.

The V2 multi-source collectors/loaders are currently being validated for safe repeatable refresh execution before unattended scheduling is enabled.

This distinction is intentional: scheduling a non-idempotent data loader can create duplicate or inconsistent data.

---

## Testing

Run:

```powershell
pytest -q
```

The test suite covers data-quality and database behavior.

Before release/submission, the current V2 branch should be validated using the current test suite together with database integrity checks.

---

## Data and Repository Hygiene

Raw and generated datasets are excluded from Git where appropriate.

Typical ignored paths include:

```text
data/raw/
data/processed/
data/external/
```

Environment secrets and runtime logs should also remain excluded.

This keeps the repository lightweight and prevents credentials or large generated datasets from being committed.

---

## Design Principles

1. Prefer legitimate public and government data sources.
2. Preserve source provenance.
3. Separate source records from canonical entities.
4. Prefer conservative matching over false-positive merges.
5. Do not invent missing contact or business information.
6. Track collection and source freshness separately.
7. Keep collection, normalization, entity resolution, persistence and presentation modular.
8. Make data-quality limitations visible.
9. Avoid using raw row counts as business counts when a source contains repeated licence/category records.
10. Keep the system extensible for additional Canadian sources.

---

## Current Limitations

The current V2 implementation deliberately does **not** claim complete Canadian business coverage.

Known limitations include:

- not every Canadian provincial/territorial registry is integrated;
- contact coverage varies substantially by source;
- employee-size information is available only where source data supports it;
- ambiguous cross-source matches are intentionally not auto-merged;
- cross-municipal/global identity resolution is not exhaustive;
- recent-business signals have source-specific meanings;
- broad decision-maker/staff-contact enrichment is not yet implemented;
- DNC/suppression integration requires further production work;
- field-level provenance can be expanded beyond the current source-record provenance;
- V2 unattended scheduled refresh is not yet enabled.

---

## V2 Coverage Report

For detailed source counts, freshness dates, entity-resolution results and limitations, see:

```text
V2_COVERAGE_FRESHNESS_REPORT.md
```

---

## Future Extensions

Potential next phases include:

- additional provincial/territorial sources
- additional municipal open-data sources
- incremental/idempotent source refresh
- automated scheduling
- snapshot-based change detection
- expanded field-level provenance
- website/contact validation
- broader employee-size enrichment
- decision-maker enrichment from compliant sources
- DNC/suppression workflows
- monitoring and alerting
- expanded dashboard analytics