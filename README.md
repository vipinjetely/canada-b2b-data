# Canada B2B Business Data Automation System

A production-oriented data pipeline for collecting, normalizing, deduplicating, enriching, storing, searching, and reviewing Canadian B2B business data using legitimate public and government data sources.

The project is designed to minimize ongoing data acquisition costs and avoid dependency on paid business-data providers such as Apollo or ZoomInfo.

## Current Status

The end-to-end pipeline is operational.

Implemented components include:

- Public government data collection
- Data normalization
- Conservative deduplication
- Supplemental business-data enrichment
- PostgreSQL persistence
- Streamlit search and review dashboard
- Automated data-quality and database tests
- FastAPI pipeline-control API
- n8n workflow orchestration
- Pipeline status monitoring and failure handling

A full pipeline execution has been successfully completed through n8n.

## Architecture

```text
Corporations Canada
        |
        v
Collection
        |
        v
Normalization
        |
        v
Deduplication
        |
        +----------------------+
        |                      |
        |               Statistics Canada
        |                    ODBus
        |                      |
        |                Normalization
        |                      |
        +-----------> Enrichment
                       |
                       v
                   PostgreSQL
                       |
                       v
                Streamlit Dashboard
```

Pipeline orchestration:

```text
n8n
 |
 v
FastAPI
 |
 v
Python Pipeline Runner
 |
 +--> Collect
 +--> Normalize
 +--> Deduplicate
 +--> Enrich
 +--> Load PostgreSQL
 |
 v
Pipeline Status
 |
 +--> Completed
 +--> Failed
 +--> Running -> Wait -> Check Again
```

## Tech Stack

- Python 3
- PostgreSQL
- Docker / Docker Compose
- Streamlit
- FastAPI
- Uvicorn
- n8n
- pandas
- psycopg
- pytest

## Project Structure

```text
collectors/       Public-data collectors
normalizers/      Source-specific normalization
deduplication/    Conservative duplicate handling
enrichment/       Supplemental data matching
database/         PostgreSQL schema, loader, and connection utilities
dashboard/        Streamlit dashboard
tests/            Data-quality and database tests
logs/             Runtime pipeline logs
data/             Downloaded and generated datasets (Git ignored)

run_pipeline.py   End-to-end pipeline runner
pipeline_api.py   FastAPI orchestration interface
docker-compose.yml
requirements.txt
.env.example
```

## Data Sources

### 1. Corporations Canada

Corporations Canada federal corporation open data is used as the primary source for the current implementation.

The collector retrieves active federal business corporation records and preserves the authoritative corporation number for identity and deduplication.

Typical fields include:

- Corporation number
- Business number
- Corporate name
- Status
- Governing legislation
- Registered address
- Province / territory
- Postal code
- Annual filing information
- Director-count information

### 2. Statistics Canada Open Database of Businesses (ODBus)

Statistics Canada's Open Database of Businesses (ODBus) is used as a supplemental enrichment source.

Potential enrichment fields include:

- Business sector
- Business subsector
- Business description
- NAICS information
- Geographic coordinates
- Employee information
- Source/provider information

ODBus is supplemental and is not treated as a complete or current master registry of all Canadian businesses.

## Data Processing

### Collection

Source-specific collectors download data from the identified public sources and save raw files locally.

### Normalization

Source data is converted into consistent field names and formats, including:

- Standardized column names
- String cleanup
- Postal-code normalization
- Business-number cleanup
- Source metadata
- Collection timestamps

### Deduplication

Corporations Canada records are deduplicated using the authoritative corporation number.

Business names alone are intentionally not used for aggressive deduplication because different legal entities may legitimately have similar or identical names.

### Enrichment

Corporations Canada records are compared with normalized ODBus records using a conservative matching strategy.

Automatic enrichment is limited to cases where the normalized business-name and province combination uniquely identifies an ODBus candidate.

Ambiguous matches are intentionally left unmatched rather than forcing potentially incorrect enrichment.

## Observed Dataset Results

During the validated development run, the database contained:

- 644,915 federal business records
- 2,115 conservatively matched ODBus records
- Approximately 0.33% automatic enrichment rate
- 13 province / territory values represented

These figures describe the validated development run and may change when upstream government datasets are refreshed.

The low enrichment rate is intentional: precision is preferred over speculative matching.

## PostgreSQL

PostgreSQL runs through Docker and stores the processed business dataset.

The `businesses` table includes:

- Core corporation fields
- Address information
- Source provenance
- ODBus enrichment fields
- Match status
- Collection timestamps

Indexes are provided for common search fields such as business name, business number, province, postal code, and NAICS.

## Streamlit Dashboard

The Streamlit dashboard queries PostgreSQL directly.

It provides:

- Total business-record count
- Enriched-record count
- Enrichment rate
- Province / territory summary
- Business-name search
- Corporation-number search
- Business-number search
- Province filter
- Status filter
- Enriched-only filter
- Configurable result limits

The dashboard does not load the complete dataset into the browser.

## Pipeline Runner

The complete pipeline can be run with:

```powershell
python run_pipeline.py
```

The runner executes the stages sequentially and writes runtime information to:

```text
logs/pipeline.log
```

A failed stage stops the pipeline and returns a non-zero exit code.

## FastAPI Pipeline Interface

Start the local API:

```powershell
python -m uvicorn pipeline_api:app --host 0.0.0.0 --port 8000
```

Available endpoints:

```text
GET  /health
GET  /pipeline/status
POST /pipeline/run
```

`POST /pipeline/run` starts the pipeline in the background.

`GET /pipeline/status` reports whether the pipeline is running, completed, or failed.

The API is intended for local development/orchestration in the current implementation. Authentication should be added before exposing it to an untrusted network.

## n8n Orchestration

n8n is used as the orchestration layer.

The implemented workflow performs:

```text
Manual Trigger
    |
Health Check
    |
Run Canada B2B Pipeline
    |
Wait 30 Seconds
    |
Check Pipeline Status
    |
Pipeline Completed?
    |
    +-- Yes --> Pipeline Completed Successfully
    |
    +-- No --> Pipeline Failed?
                   |
                   +-- Yes --> Pipeline Execution Failed
                   |
                   +-- No --> Wait 30 Seconds and check again
```

This allows a single n8n workflow execution to start the pipeline and monitor it until a terminal state is reached.

## Local Setup

### 1. Create a virtual environment

```powershell
python -m venv .venv
```

### 2. Activate it on Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Copy:

```text
.env.example
```

to:

```text
.env
```

and provide the local PostgreSQL credentials.

Do not commit `.env`.

### 5. Start PostgreSQL

```powershell
docker compose up -d postgres
```

### 6. Apply the database schema

Apply:

```text
database/schema.sql
```

to the PostgreSQL database before the first data load.

### 7. Run the pipeline

```powershell
python run_pipeline.py
```

### 8. Start the dashboard

```powershell
streamlit run dashboard/app.py
```

### 9. Start the orchestration API

```powershell
python -m uvicorn pipeline_api:app --host 0.0.0.0 --port 8000
```

## Testing

Run:

```powershell
pytest -v
```

The test suite validates areas including:

- Dataset availability
- Required columns
- Corporation-number integrity
- Corporation-number uniqueness
- Business-name availability
- Source provenance
- PostgreSQL connectivity
- Database population
- Database corporation-number uniqueness

The validated development run passed all implemented tests.

## Data and Repository Hygiene

Downloaded and generated datasets are intentionally excluded from Git:

```text
data/raw/
data/processed/
data/external/
```

Environment secrets and runtime logs are also excluded.

This keeps the repository lightweight and prevents local credentials from being committed.

## Design Principles

The project follows these principles:

1. Prefer legitimate public and government data sources.
2. Avoid unnecessary dependency on paid business-data providers.
3. Preserve source provenance.
4. Prefer conservative matching over fabricated or speculative enrichment.
5. Keep collection, normalization, deduplication, enrichment, persistence, and presentation as separate components.
6. Make the pipeline reproducible and observable.
7. Do not invent missing phone numbers, email addresses, websites, or other contact information.

## Current Limitations

The current implementation has deliberate limitations:

- Corporations Canada covers federal corporations and is not a complete registry of every Canadian business.
- Provincial and territorial registries are not yet integrated.
- ODBus is used as a supplemental dataset and may contain older records.
- Conservative matching produces a relatively low enrichment rate.
- Contact-data enrichment such as verified websites, phone numbers, and email addresses has not been fabricated or inferred.
- The FastAPI control interface is currently designed for local orchestration rather than public deployment.
- Additional public sources can be added through new collector and normalization modules.

## Future Extensions

Potential next phases include:

- Provincial and territorial public registries
- Additional legitimate open-data sources
- Website discovery from public business information
- Contact-data validation
- Improved multi-stage entity resolution with confidence scoring
- Incremental database updates
- Pipeline scheduling
- Monitoring and alerting
- Containerization of additional application services
- Expanded dashboard analytics