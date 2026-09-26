# Canada B2B Business Data Automation System

A production-oriented data pipeline for discovering, classifying, resolving, enriching, validating, storing, monitoring, and reviewing Canadian business/location data from legitimate public and open-data sources.

The project is designed around four principles:

- broad Canada-wide discovery,
- conservative identity resolution,
- evidence-based enrichment,
- transparent data quality and limitations.

Missing information is not fabricated. Aggregate statistics are not assigned to individual businesses, ambiguous identity matches are not automatically merged, and raw place/source counts are not presented as legal-business counts.

---

## V3 Current Status

The V3 operating-location layer currently contains:

| Metric | Current Result |
|---|---:|
| Business/location candidates | **1,183,392** |
| With phone | **1,110,274** |
| With email | **600,645** |
| With website | **992,647** |
| Sales-ready by V3 completeness rule | **724,614** |
| Verified location-level employee evidence | **3,653** |
| High source-confidence records | **461,884** |
| Automated V3 transformation stages | **11** |
| Current automated tests | **29 passed** |

These records represent classified business/location candidates, not a claim of 1,183,392 nationally unique legal companies.

The V2 government/registry layer remains preserved separately and contains **849,849 canonical entities** with **948,765 provenance records** across six source jurisdictions.

---

## Architecture

```text
Open / Government Data Sources
            |
            v
     Canada-wide Discovery
            |
            v
       Classification
   Business / Non-business
        / Review
            |
            v
   Operating-Location Layer
            |
            v
 Normalization / Identity Keys
            |
            v
 Conservative Entity Resolution
            |
       +----+----+
       |         |
       v         v
 Government   Contact /
 Validation   Attribute Data
       |         |
       +----+----+
            |
            v
 Evidence-based Enrichment
            |
            v
 Quality / Readiness Scoring
            |
            v
 Daily Change Detection
            |
            v
        PostgreSQL
            |
       +----+----+
       |         |
       v         v
 Change History  Streamlit
 / Evidence      Dashboard
```

The V3 design deliberately separates operating locations, identity-resolution keys, employee evidence, contact evidence, change history, and the current database snapshot.

---

## Tech Stack

- Python 3
- PostgreSQL
- Docker / Docker Compose
- DuckDB
- pandas
- psycopg
- Streamlit
- FastAPI / Uvicorn foundation
- n8n orchestration foundation
- Windows Task Scheduler for the V3 daily runner
- pytest

---

## V3 Pipeline

The production V3 transformation pipeline is defined in:

```text
run_v3_pipeline.py
```

It currently contains **11 ordered stages**:

1. Classify Canadian Overture places
2. Build strict business candidates
3. Prepare employee-enrichment fields
4. Build operating-location layer
5. Build entity-resolution foundation
6. Build verified Vancouver employee matches
7. Apply verified employee enrichment
8. Score record quality and readiness
9. Detect daily new and changed businesses
10. Persist daily change history
11. Load validated V3 data into PostgreSQL

A failure in a stage prevents later stages from being treated as successfully completed.

---

## Canada-wide Discovery

V3 uses a Canada-wide place/business discovery layer and then applies explicit classification rules.

The discovery layer is not treated as a legal-company registry.

A source record may represent:

- a business,
- a branch/location,
- a service location,
- an institution,
- a public place,
- another point of interest.

For that reason, records are classified before entering the strict business-candidate layer.

The current strict V3 output contains:

```text
1,183,392 business/location candidates
```

Permanently closed records are excluded from the strict candidate output where the upstream status supports that determination.

An unknown operating-status value is not automatically interpreted as proof that a business is currently open.

---

## Business Classification

Classification separates records into:

```text
BUSINESS
NON_BUSINESS
REVIEW
```

Only the strict `BUSINESS` output proceeds into the current V3 business-location dataset.

Ambiguous categories remain in `REVIEW` instead of being forced into the business dataset.

This approach intentionally prioritizes accuracy over inflating the record count.

---

## Operating Locations vs Business Entities

V3 preserves operating locations separately from business/entity identity.

Current operating-location records:

```text
1,183,392
```

Current unique normalized business names:

```text
928,895
```

Repeated names are expected because chains and multi-location organizations can operate many locations.

The system therefore does not assume:

```text
one location = one legal company
```

and does not use a shared website domain alone as proof that two locations are the same business entity.

---

## Conservative Entity Resolution

The V3 entity-resolution foundation builds conservative location identity keys using combinations such as:

- normalized business name + postal code,
- normalized business name + phone,
- normalized business name + appropriate identity domain.

Shared/platform domains are not treated as strong identity keys.

Current resolution foundation:

```text
Total locations:              1,183,392
Name + postal:                1,145,288
Name + phone fallback:           19,875
Name + domain fallback:           7,049
Insufficient strong identity:    11,180
Unique conservative keys:     1,152,703
```

These conservative keys support entity resolution but are not presented as a final count of unique Canadian legal companies.

---

## Contact Coverage

Current V3 contact availability:

```text
Phone:    1,110,274
Email:      600,645
Website:    992,647
```

Contact availability is measured independently from employee verification and decision-maker verification.

A phone number, email address, or website supplied by a source is not automatically interpreted as a named decision-maker contact.

---

## Employee Count / Employee Size

Employee information is handled using an evidence-first model.

V3 supports:

```text
employee_count
employee_size_bucket
employee_count_type
employee_evidence_source
employee_evidence_url
employee_verified_at
employee_evidence_scope
```

Employee count types are:

```text
VERIFIED
ESTIMATED
UNKNOWN
```

Evidence scope distinguishes:

```text
LOCATION
COMPANY_GLOBAL
```

This distinction prevents a global corporate headcount from being incorrectly assigned to an individual branch/location.

### Current verified employee coverage

A conservative match between Vancouver government business data and V3 operating locations currently provides:

```text
3,653 VERIFIED location-level employee records
```

All other records remain `UNKNOWN` unless suitable evidence exists.

No employee count is fabricated from aggregate industry or geographic statistics.

Public aggregate Statistics Canada employee-size distributions may be useful for benchmarking, but they are not assigned to named businesses as individual facts.

---

## Employee Size Buckets

Where supported by record-level evidence, the target employee-size model supports business-size classification.

The system does not force a bucket when the underlying evidence is insufficient.

This is particularly important where a public statistical source provides aggregate counts rather than named-company headcount.

---

## Quality and Sales Readiness

Each V3 record receives a transparent completeness/quality score based on available identity, address, contact, category, source-confidence, and verified employee evidence.

Current output:

```text
Sales-ready:   724,614
Partial:       426,555
Incomplete:     32,223
Average score:   81.22
```

`SALES_READY` is a data-completeness/readiness classification.

It does **not** mean that every field has been independently verified, nor does it mean that every record represents a nationally unique legal company.

The current rule requires:

- quality score >= 80,
- phone available,
- email or website available.

---

## Source Confidence

Source/place confidence is retained separately from the V3 quality score.

Current high source-confidence records:

```text
461,884
```

Source confidence should not be interpreted as independent verification of every contact field.

---

## Decision-maker / Staff Contact Enrichment

The architecture supports contact-evidence storage for fields such as:

- full name,
- job title,
- contact role,
- email,
- phone,
- evidence source,
- evidence text,
- verification timestamp,
- confidence/review status.

Exploratory decision-maker extraction was tested separately.

The current production V3 database does **not** claim verified Canada-wide decision-maker coverage.

Candidates without sufficiently reliable evidence remain outside the production verified-contact layer.

---

## PostgreSQL V3 Model

Primary V3 tables:

```text
v3_business_locations
v3_location_sources
v3_employee_evidence
v3_contact_evidence
v3_location_change_history
v3_pipeline_runs
```

### `v3_business_locations`

Stores the current business/location snapshot, including:

- identity fields,
- address,
- category,
- contact availability,
- operating status,
- source confidence,
- conservative resolution key,
- employee fields,
- quality score,
- readiness classification,
- source-confidence band,
- DNC flag.

### Evidence tables

Employee and contact evidence are separated from the main location record so future enrichment can retain evidence scope, source, verification time and review state.

### Change history

Change history is deliberately preserved independently from current-snapshot refreshes.

Historical location IDs are therefore not deleted merely because a current snapshot changes.

---

## Daily Change Detection

V3 compares the current processed location dataset with the existing PostgreSQL snapshot.

Tracked changes include fields such as:

- business name,
- address,
- city,
- province,
- postal code,
- phone,
- email,
- website,
- category,
- operating status,
- employee count,
- employee bucket,
- employee evidence type.

Records are classified as:

```text
NEW
CHANGED
UNCHANGED
REMOVED
```

Actionable changes can be persisted in:

```text
v3_location_change_history
```

The initial validated baseline produced:

```text
NEW:             0
CHANGED:         0
UNCHANGED: 1,183,392
REMOVED:         0
```

This baseline verifies that the processed location snapshot and the PostgreSQL snapshot were aligned at the time of comparison.

---

## Automated Scheduling

V3 includes:

```text
run_v3_scheduled.py
```

The wrapper provides:

- single-run locking,
- scheduler logging,
- pipeline exit-code handling,
- exception handling,
- lock cleanup.

A Windows Task Scheduler task is configured for daily execution at:

```text
02:00 local time
```

The scheduler wrapper and 11-stage pipeline are implemented.

The first unattended scheduled attempt was interrupted during the initial classification stage, so a successful unattended end-to-end scheduled execution is **not yet claimed**.

The current raw Overture acquisition/download step is also outside the 11-stage scheduled transformation pipeline.

These limitations are documented rather than hidden.

---

## Streamlit V3 Dashboard

Start the V3 dashboard with:

```powershell
streamlit run dashboard/app_v3.py
```

The dashboard queries PostgreSQL and provides:

- business/location total,
- phone availability,
- email availability,
- website availability,
- sales-readiness count,
- verified employee count,
- high source-confidence count,
- average quality score,
- province/territory filtering,
- category filtering,
- readiness filtering,
- source-confidence filtering,
- contact filtering,
- employee-evidence filtering,
- minimum-quality filtering,
- business search,
- daily change-history view.

The dashboard does not load the full national dataset into the browser.

---

## V2 Government / Registry Foundation

V2 remains preserved as a separate government/registry-oriented layer.

Current V2 database state:

```text
Canonical entities:          849,849
Source provenance records:   948,765
Orphan provenance records:         0
Duplicate Federal IDs:             0
Duplicate Provincial IDs:          0
```

Integrated V2 jurisdictions/sources include:

- Corporations Canada
- Vancouver Business Licences
- Toronto Business Licences / Permits
- Edmonton Business Licences
- Calgary Business Licences
- Québec RBQ Active Licences

The V3 location count and V2 canonical count must **not** simply be added together because the two layers can overlap and represent different identity granularities.

For detailed V2 source coverage and freshness information, see:

```text
V2_COVERAGE_FRESHNESS_REPORT.md
```

---

## Testing

Run:

```powershell
pytest -q
```

Current validated result:

```text
29 passed
```

Tests cover the existing project plus V3 integrity requirements including:

- required V3 artifacts,
- strict candidate count,
- location-layer preservation,
- resolution-layer preservation,
- enrichment-layer preservation,
- unique location IDs,
- verified employee count,
- employee evidence completeness,
- location-level evidence scope,
- prevention of fabricated employee values on `UNKNOWN` records.

---

## Local Setup

### 1. Create the environment

```powershell
python -m venv .venv
```

### 2. Activate on Windows

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure PostgreSQL

Copy:

```text
.env.example
```

to:

```text
.env
```

and provide local PostgreSQL configuration.

Do not commit `.env`.

### 5. Start PostgreSQL

```powershell
docker compose up -d postgres
```

### 6. Apply the V3 schema

Apply:

```text
database/v3_schema.sql
```

before the first V3 database load.

### 7. Run V3 pipeline

```powershell
python run_v3_pipeline.py
```

### 8. Start V3 dashboard

```powershell
streamlit run dashboard/app_v3.py
```

---

## Repository Hygiene

Large raw and generated datasets are excluded from Git.

Runtime logs, scheduler lock files, local environment configuration, and generated V3 Parquet/CSV files are also excluded where appropriate.

The repository contains code, schemas, tests and documentation rather than the full multi-gigabyte working dataset.

---

## Accuracy Principles

1. Do not manufacture missing fields.
2. Do not treat raw source rows as unique businesses without checking source structure.
3. Do not treat every place/POI as a legal company.
4. Do not interpret unknown operating status as confirmed open.
5. Keep locations and legal/entity identity conceptually separate.
6. Prefer conservative matching over false-positive merging.
7. Preserve evidence scope for employee and contact information.
8. Do not assign aggregate employee statistics to individual named businesses.
9. Keep source confidence separate from record completeness.
10. Keep incomplete/review records visible instead of artificially forcing them into high-confidence output.
11. Preserve change history separately from the current snapshot.
12. Document implementation limitations explicitly.

---

## Current Limitations

The current implementation deliberately does **not** claim complete coverage of every operating business in Canada.

Known limitations include:

- the 1,183,392 V3 records are business/location candidates rather than a final national legal-entity count;
- many upstream records do not provide an explicit operating-status value;
- verified individual employee coverage is currently limited to evidence-supported records;
- broad production decision-maker/staff enrichment is not yet available;
- DNC/suppression schema support exists, but a comprehensive DNC ingestion/verification workflow is not yet implemented;
- raw Canada-wide source acquisition is not yet part of the daily scheduled transformation runner;
- the first unattended V3 scheduled execution did not complete end-to-end successfully;
- evidence/source child-table population can be expanded further;
- current snapshot loading can be improved toward fully incremental/upsert-based persistence;
- `first_seen` semantics can be strengthened when the snapshot loader is converted to incremental persistence;
- additional government/provincial validation sources can improve legal-entity resolution and employee coverage.

---

## Project Goal

The purpose of this trial implementation is not to manually finish every Canadian business record.

It demonstrates a scalable architecture for:

```text
discovery
    ->
classification
    ->
normalization
    ->
identity resolution
    ->
government/public validation
    ->
evidence-based enrichment
    ->
quality scoring
    ->
change detection
    ->
PostgreSQL persistence
    ->
dashboard / export / downstream integration
```

The architecture is designed so additional compliant Canadian sources, employee evidence, decision-maker evidence, validation rules and CRM integrations can be added without replacing the core pipeline.