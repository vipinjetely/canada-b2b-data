# Canada B2B Business Data Automation System
## V2 Coverage & Freshness Report

**Report Date:** 26 September 2026  
**Revision:** V2 – Coverage, Freshness & Provenance Enhancement

---

## 1. Executive Summary

V2 expands the original federal-first dataset into a multi-source
canonical business data system using current Canadian federal,
provincial and municipal public datasets.

The objective of this revision was not to inflate the database with
duplicate raw records. Instead, the system preserves source-level
records while resolving them conservatively into canonical business
entities.

### Current V2 Result

- **849,849 canonical business entities**
- **948,765 source provenance records**
- **6 active public-data sources / registry jurisdictions**
- **0 orphan provenance records**
- **0 duplicate Federal Corporation IDs**
- **0 duplicate Provincial Registry IDs**
- All six source loads completed with **0 failed records**

The source collection cycle used for this report was completed on
25 September 2026.

---

## 2. V1 to V2 Coverage Expansion

The original implementation was primarily based on the Corporations
Canada federal dataset.

V2 retains that authoritative federal foundation and adds selected
current provincial and municipal business/licensing datasets.

| Registry Jurisdiction | Canonical Entities |
|---|---:|
| Federal | 645,005 |
| Vancouver, BC | 62,357 |
| Québec, QC | 46,570 |
| Edmonton, AB | 39,714 |
| Toronto, ON | 33,437 |
| Calgary, AB | 22,766 |
| **Total** | **849,849** |

The municipal/provincial integrations therefore add **204,844**
canonical jurisdiction-level entities beyond the original federal
entity count.

These counts should not be interpreted as a claim that every entity is
a nationally unique legal business across all possible Canadian
registries. Cross-source matching is deliberately conservative to
minimize false merges.

---

## 3. Current Source Freshness

| Source | Jurisdiction | Upstream Source Date | Collected |
|---|---|---|---|
| Corporations Canada | Federal | 2026-09-25 | 2026-09-25 |
| Vancouver Business Licences | Vancouver, BC | 2026-09-24 | 2026-09-25 |
| Toronto Business Licences | Toronto, ON | 2026-09-25 | 2026-09-25 |
| Edmonton Business Licences | Edmonton, AB | 2026-09-23 | 2026-09-25 |
| Calgary Business Licences | Calgary, AB | Not reliably supplied upstream | 2026-09-25 |
| Québec RBQ Active Licences | Québec, QC | 2026-09-25 | 2026-09-25 |

The system tracks **source update time** separately from
**collection time**.

When an upstream source does not provide a reliable update timestamp,
the system leaves that value blank rather than manufacturing a
freshness date.

---

## 4. Provenance Coverage

V2 stores raw/source-level records separately from canonical business
entities.

### Verified Database State

- Canonical entities: **849,849**
- Source provenance records: **948,765**
- Orphan provenance records: **0**

This means source records remain traceable to the canonical entity to
which they were linked.

The design allows multiple source records or licences to resolve to one
canonical entity without losing the original source evidence.

---

## 5. Entity Resolution & Deduplication

V2 uses conservative multi-factor entity resolution.

Strong identifiers are preferred whenever available, including:

- Federal Corporation Number
- Québec NEQ / provincial registry identifier
- Source licence identifiers

Cross-source matching uses combinations of normalized business name,
city, postal/address information and unique-name constraints.

Ambiguous name-only matches are not automatically merged.

### Integrity Validation

- Duplicate Federal Corporation IDs: **0**
- Duplicate Provincial Registry IDs within jurisdiction: **0**
- Orphan provenance links: **0**

The objective is to minimize false-positive merges rather than force
maximum matching percentages.

---

## 6. Québec RBQ Expansion

The Québec RBQ active-licence source contained:

- **927,338 raw CSV rows**
- **49,770 usable unique active licence records**
- **49,659 unique valid NEQs**

The large difference between raw rows and unique licences demonstrates
why raw dataset row counts cannot safely be treated as business counts.

Entity resolution produced:

- **3,161 strong Federal match records**
- **46,570 Québec-local canonical entities**
- **511 weaker Federal match candidates retained without automatic
  Federal merging**
- **39 local licence records collapsed into existing Québec canonical
  identities**

### Québec Contact Coverage

Among the 46,570 Québec-local canonical entities:

- **46,564 have phone data**
- **44,196 have email data**
- **46,564 have address data**

Strong Québec-to-Federal matches also enriched existing Federal
entities where those fields were previously missing.

---

## 7. Contact & Attribute Coverage

Contact and enrichment availability varies significantly by source.

Verified examples include:

- Federal entities with phone after current enrichment: **3,471**
- Federal entities with email after current enrichment: **2,990**
- Québec entities with phone: **46,564**
- Québec entities with email: **44,196**
- Toronto entities with phone: **12,479**

Missing phone, email, employee count, industry or other attributes are
retained as missing rather than guessed or synthetically generated.

This is intentional for data-quality and provenance reasons.

---

## 8. Recent Business / Activity Signals

The V2 schema supports:

- `is_new_1d`
- `is_new_7d`
- `is_new_30d`

Current verified jurisdiction signals include:

| Jurisdiction | 7-Day Signal | 30-Day Signal |
|---|---:|---:|
| Vancouver, BC | 105 | 612 |
| Edmonton, AB | 389 | 2,530 |
| Toronto, ON | 120 | 480 |
| Calgary, AB | 10 | 230 |

These values are deliberately described as **recent activity signals**.

They must not universally be interpreted as newly incorporated
businesses because individual sources expose different date semantics,
such as licence issuance or recent licence activity.

---

## 9. Pipeline Load Results

The V2 database records pipeline execution history.

Verified source loads:

| Source Load | Collected | Inserted | Updated | Deduplicated / Linked | Failed |
|---|---:|---:|---:|---:|---:|
| Corporations Canada | 645,005 | 645,005 | 0 | 0 | 0 |
| Vancouver | 153,460 | 62,357 | 0 | 91,103 | 0 |
| Toronto | 37,531 | 33,437 | 1,228 | 4,094 | 0 |
| Edmonton | 40,162 | 39,714 | 32 | 448 | 0 |
| Calgary | 22,837 | 22,766 | 0 | 71 | 0 |
| Québec RBQ | 49,770 | 46,570 | 3,158 | 3,200 | 0 |

All six recorded source loads completed without failed records.

---

## 10. Dashboard

The Streamlit V2 dashboard operates on the canonical
`business_entities` layer and provides:

- Canonical entity totals
- Phone/email availability metrics
- Registry jurisdiction filtering
- Business-name and identifier search
- Status filtering
- Industry/licence-category filtering
- Contact-availability filtering
- 7-day and 30-day recent-activity filtering
- Jurisdiction-level coverage summary
- Source freshness/provenance view
- CSV export of filtered results

The dashboard also explicitly displays the limitation that recent
signals have source-specific meanings.

---

## 11. Important Coverage Limitation

V2 should **not** be described as a complete database of every Canadian
business.

Canadian business population statistics and raw registry/licensing
record counts are not directly equivalent to unique named businesses
available through openly reusable business-level datasets.

The current system therefore reports:

- verified canonical entity counts,
- source provenance,
- source freshness,
- actual enrichment availability,
- and known limitations,

rather than using an unsupported nationwide completeness percentage.

---

## 12. Remaining Production Considerations

Further expansion can be performed by adding additional provincial,
municipal or licensed commercial sources when their:

1. data freshness is suitable,
2. business-level identity fields are usable,
3. licensing permits the intended use,
4. provenance can be retained, and
5. entity resolution can be performed safely.

Additional production work may also include:

- broader contact and decision-maker enrichment,
- additional employee-size coverage,
- field-level provenance expansion,
- DNC/suppression-list integration,
- scheduled refresh execution,
- change-history expansion,
- and additional provincial source coverage.

---

## 13. V2 Validation Snapshot

As of this revision:

**Canonical entities:** 849,849  
**Source provenance records:** 948,765  
**Active sources:** 6  
**Orphan provenance:** 0  
**Duplicate Federal IDs:** 0  
**Duplicate Provincial IDs:** 0  
**Failed records in recorded source loads:** 0  

V2 prioritizes **freshness, traceability, conservative entity
resolution and reproducible source evidence** over inflated raw-record
counts.