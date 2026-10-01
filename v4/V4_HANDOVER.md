# Canada B2B Data Automation System — V4 Handover

## Final Validation

**Overall status:** PASS

**Requirements passed:** 6/6

**Requirements failed:** 0/6

The V4 pipeline has been validated against the six defined requirements using the automated master audit.

## 1. Registry Integration

- Status: **PASS**
- Quebec registry records: **2,958,846**
- Unique registry IDs: **2,958,846**
- Duplicate registry IDs: **0**

## 2. New-Business Detection and Freshness

- Status: **PASS**
- Calendar validation date: **2026-10-01**
- Latest source registration date: **2026-09-15**
- Source lag: **16 days**
- Calendar today: **0**
- Calendar last 7 days: **0**
- Calendar last 30 days: **3,327**
- Latest dataset-relative 7 days: **2,100**
- Latest dataset-relative 30 days: **8,359**

## 3. Employee-Size Classification

- Status: **PASS**
- Registry records: **2,958,846**
- Verified employee ranges: **2,884,247**
- Records with employee-size bucket: **2,957,847**

Employee size is retained as evidence-backed registry ranges rather than converting ranges into invented exact employee counts.

## 4. Evidence-Backed Decision Makers

- Status: **PASS**
- Verified decision-makers demonstrated: **3**
- Covered business entities: **2**
- Missing person names: **0**
- Missing job titles: **0**
- Missing evidence URLs: **0**

The decision-maker workflow rejects generated people, generated titles, unsupported role categories, unsupported source types and unreachable evidence URLs.

## 5. Field-Level Provenance

- Status: **PASS**
- Registry entities: **2,958,846**
- Registry field-evidence rows: **29,443,592**
- Missing registry source URLs: **0**
- Missing registry verification timestamps: **0**
- Decision-maker entities: **1**
- Decision-maker field-evidence rows: **6**
- Missing decision-maker source URLs: **0**
- Missing decision-maker verification timestamps: **0**

## 6. Website Quality Cleanup

- Status: **PASS**
- Business rows before/after: **1,183,392 / 1,183,392**
- Row count preserved: **YES**
- Nonblank websites before: **992,646**
- Nonblank websites after: **971,162**
- Website values quarantined: **21,485**
- Blocked website values remaining: **0**
- Karan-flagged categories detected: **16,460**

Underlying business records are preserved; rejected website values are quarantined rather than deleting businesses.

## Known Limitations

1. Quebec new-business results are constrained by the freshness of the official source dataset. The latest registration date currently present is 2026-09-15, with a 16-day source lag at validation time.
2. Calendar last-7-day and last-30-day results must not be confused with dataset-relative windows. Both are reported separately.
3. Decision-maker enrichment is evidence-first and currently demonstrates a verified sample rather than claiming complete decision-maker coverage for all businesses.
4. Decision-maker names and titles are accepted only when supported by a reachable public evidence URL; generated or guessed people/titles are prohibited.
5. Website cleanup quarantines directory, social, search/map and other blocked website values while preserving the underlying business records.
6. Alberta official registry search access was audited as restricted/search-based; no public bulk dump or confirmed public API was treated as available.

## Validation Evidence

Master validation:

`C:\Projects\canada-b2b-data\data\processed\v4\audit\karan_six_point_validation.json`

Quebec registry:

`C:\Projects\canada-b2b-data\data\processed\v4\registry\quebec_registry.parquet`

New-business evidence:

`C:\Projects\canada-b2b-data\data\processed\v4\new_businesses\quebec_new_business_detection.json`

Decision-maker sample:

`C:\Projects\canada-b2b-data\data\processed\v4\enrichment\decision_maker_sample.csv`

Decision-maker evidence:

`C:\Projects\canada-b2b-data\data\processed\v4\enrichment\decision_maker_sample_evidence.json`

Registry field provenance:

`C:\Projects\canada-b2b-data\data\processed\v4\provenance\quebec_field_provenance.parquet`

Decision-maker field provenance:

`C:\Projects\canada-b2b-data\data\processed\v4\provenance\decision_maker_field_provenance.parquet`

Clean website dataset:

`C:\Projects\canada-b2b-data\data\processed\v4\website_quality\business_locations_websites_cleaned.parquet`

Website quarantine:

`C:\Projects\canada-b2b-data\data\processed\v4\website_quality\website_quarantine.parquet`

---

Generated from the final automated V4 validation evidence.

Generated at UTC: `2026-10-01T22:16:33.277333+00:00`
