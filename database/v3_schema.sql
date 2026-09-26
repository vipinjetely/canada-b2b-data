-- ============================================================
-- Canada B2B Data Automation System
-- V3 PostgreSQL Schema
--
-- V3 is intentionally isolated from the existing V1/V2 tables.
-- It models operating business locations separately from legal
-- or canonical business entities.
-- ============================================================


-- ------------------------------------------------------------
-- 1. V3 operating business locations
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS v3_business_locations (
    id BIGSERIAL PRIMARY KEY,

    location_id TEXT NOT NULL UNIQUE,

    business_name TEXT,
    normalized_name TEXT,

    street TEXT,
    city TEXT,
    province TEXT,
    postal_code TEXT,
    country TEXT DEFAULT 'CA',

    basic_category TEXT,

    phone TEXT,
    email TEXT,
    website TEXT,
    website_domain TEXT,

    operating_status TEXT,

    source_confidence NUMERIC(8,6),

    conservative_location_key TEXT,
    resolution_method TEXT,

    employee_count INTEGER,
    employee_size_bucket TEXT,

    employee_count_type TEXT NOT NULL DEFAULT 'UNKNOWN',

    employee_evidence_source TEXT,
    employee_evidence_url TEXT,
    employee_evidence_scope TEXT,
    employee_verified_at TIMESTAMPTZ,

    do_not_call BOOLEAN NOT NULL DEFAULT FALSE,

    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT v3_employee_type_check
        CHECK (
            employee_count_type IN (
                'VERIFIED',
                'ESTIMATED',
                'UNKNOWN'
            )
        ),

    CONSTRAINT v3_employee_scope_check
        CHECK (
            employee_evidence_scope IS NULL
            OR employee_evidence_scope IN (
                'LOCATION',
                'COMPANY_GLOBAL'
            )
        ),

    CONSTRAINT v3_employee_count_check
        CHECK (
            employee_count IS NULL
            OR employee_count >= 0
        )
);


-- ------------------------------------------------------------
-- 2. Source / provenance records
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS v3_location_sources (
    id BIGSERIAL PRIMARY KEY,

    location_id TEXT NOT NULL,

    source_name TEXT NOT NULL,
    source_record_id TEXT,
    source_url TEXT,

    source_updated_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ,

    raw_reference TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_v3_location_source
        FOREIGN KEY (location_id)
        REFERENCES v3_business_locations(location_id)
        ON DELETE CASCADE
);


-- ------------------------------------------------------------
-- 3. Employee evidence history
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS v3_employee_evidence (
    id BIGSERIAL PRIMARY KEY,

    location_id TEXT NOT NULL,

    employee_count INTEGER,
    employee_size_bucket TEXT,

    evidence_type TEXT NOT NULL,
    evidence_scope TEXT NOT NULL,

    source_name TEXT NOT NULL,
    source_url TEXT,

    evidence_text TEXT,

    verified_at TIMESTAMPTZ,

    confidence_score NUMERIC(8,6),

    review_status TEXT NOT NULL DEFAULT 'REVIEW',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_v3_employee_location
        FOREIGN KEY (location_id)
        REFERENCES v3_business_locations(location_id)
        ON DELETE CASCADE,

    CONSTRAINT v3_evidence_scope_check
        CHECK (
            evidence_scope IN (
                'LOCATION',
                'COMPANY_GLOBAL'
            )
        ),

    CONSTRAINT v3_review_status_check
        CHECK (
            review_status IN (
                'VERIFIED',
                'REVIEW',
                'REJECTED'
            )
        )
);


-- ------------------------------------------------------------
-- 4. Decision-maker evidence
--
-- REVIEW by default. Extracted contacts must not automatically
-- become verified production contacts.
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS v3_contact_evidence (
    id BIGSERIAL PRIMARY KEY,

    location_id TEXT,

    full_name TEXT,
    job_title TEXT,
    contact_role TEXT,

    email TEXT,
    phone TEXT,

    evidence_scope TEXT,

    source_url TEXT,
    evidence_text TEXT,

    confidence_score NUMERIC(8,6),

    review_status TEXT NOT NULL DEFAULT 'REVIEW',

    verified_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_v3_contact_location
        FOREIGN KEY (location_id)
        REFERENCES v3_business_locations(location_id)
        ON DELETE CASCADE,

    CONSTRAINT v3_contact_review_check
        CHECK (
            review_status IN (
                'VERIFIED',
                'REVIEW',
                'REJECTED'
            )
        )
);


-- ------------------------------------------------------------
-- 5. Location change history
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS v3_location_change_history (
    id BIGSERIAL PRIMARY KEY,

    location_id TEXT NOT NULL,

    change_type TEXT NOT NULL,
    field_name TEXT,

    old_value TEXT,
    new_value TEXT,

    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    source_name TEXT,

    CONSTRAINT fk_v3_change_location
        FOREIGN KEY (location_id)
        REFERENCES v3_business_locations(location_id)
        ON DELETE CASCADE
);


-- ------------------------------------------------------------
-- 6. Pipeline run history
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS v3_pipeline_runs (
    id BIGSERIAL PRIMARY KEY,

    run_id TEXT NOT NULL UNIQUE,

    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,

    status TEXT NOT NULL,

    records_input BIGINT DEFAULT 0,
    records_output BIGINT DEFAULT 0,

    records_inserted BIGINT DEFAULT 0,
    records_updated BIGINT DEFAULT 0,
    records_failed BIGINT DEFAULT 0,

    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT v3_pipeline_status_check
        CHECK (
            status IN (
                'RUNNING',
                'SUCCESS',
                'FAILED'
            )
        )
);


-- ------------------------------------------------------------
-- 7. Useful indexes
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_v3_location_name
    ON v3_business_locations (business_name);

CREATE INDEX IF NOT EXISTS idx_v3_location_province
    ON v3_business_locations (province);

CREATE INDEX IF NOT EXISTS idx_v3_location_city
    ON v3_business_locations (city);

CREATE INDEX IF NOT EXISTS idx_v3_location_postal
    ON v3_business_locations (postal_code);

CREATE INDEX IF NOT EXISTS idx_v3_location_category
    ON v3_business_locations (basic_category);

CREATE INDEX IF NOT EXISTS idx_v3_location_phone
    ON v3_business_locations (phone);

CREATE INDEX IF NOT EXISTS idx_v3_location_email
    ON v3_business_locations (email);

CREATE INDEX IF NOT EXISTS idx_v3_location_domain
    ON v3_business_locations (website_domain);

CREATE INDEX IF NOT EXISTS idx_v3_employee_type
    ON v3_business_locations (employee_count_type);

CREATE INDEX IF NOT EXISTS idx_v3_employee_bucket
    ON v3_business_locations (employee_size_bucket);

CREATE INDEX IF NOT EXISTS idx_v3_dnc
    ON v3_business_locations (do_not_call);

CREATE INDEX IF NOT EXISTS idx_v3_location_key
    ON v3_business_locations (conservative_location_key);

CREATE INDEX IF NOT EXISTS idx_v3_source_location
    ON v3_location_sources (location_id);

CREATE INDEX IF NOT EXISTS idx_v3_employee_evidence_location
    ON v3_employee_evidence (location_id);

CREATE INDEX IF NOT EXISTS idx_v3_contact_evidence_location
    ON v3_contact_evidence (location_id);

CREATE INDEX IF NOT EXISTS idx_v3_change_location
    ON v3_location_change_history (location_id);

CREATE INDEX IF NOT EXISTS idx_v3_change_detected
    ON v3_location_change_history (detected_at);

    -- ------------------------------------------------------------
-- 8. V3 record-quality / sales-readiness fields
-- ------------------------------------------------------------

ALTER TABLE v3_business_locations
    ADD COLUMN IF NOT EXISTS quality_score INTEGER;

ALTER TABLE v3_business_locations
    ADD COLUMN IF NOT EXISTS record_readiness TEXT;

ALTER TABLE v3_business_locations
    ADD COLUMN IF NOT EXISTS source_confidence_band TEXT;

ALTER TABLE v3_business_locations
    DROP CONSTRAINT IF EXISTS v3_quality_score_check;

ALTER TABLE v3_business_locations
    ADD CONSTRAINT v3_quality_score_check
        CHECK (
            quality_score IS NULL
            OR (
                quality_score >= 0
                AND quality_score <= 100
            )
        );

ALTER TABLE v3_business_locations
    DROP CONSTRAINT IF EXISTS v3_record_readiness_check;

ALTER TABLE v3_business_locations
    ADD CONSTRAINT v3_record_readiness_check
        CHECK (
            record_readiness IS NULL
            OR record_readiness IN (
                'SALES_READY',
                'PARTIAL',
                'INCOMPLETE'
            )
        );

ALTER TABLE v3_business_locations
    DROP CONSTRAINT IF EXISTS v3_source_confidence_band_check;

ALTER TABLE v3_business_locations
    ADD CONSTRAINT v3_source_confidence_band_check
        CHECK (
            source_confidence_band IS NULL
            OR source_confidence_band IN (
                'HIGH',
                'MEDIUM',
                'LOW'
            )
        );

CREATE INDEX IF NOT EXISTS idx_v3_quality_score
    ON v3_business_locations (quality_score);

CREATE INDEX IF NOT EXISTS idx_v3_record_readiness
    ON v3_business_locations (record_readiness);

CREATE INDEX IF NOT EXISTS idx_v3_source_confidence_band
    ON v3_business_locations (source_confidence_band);

    -- ------------------------------------------------------------
-- 9. Preserve change history across snapshot refreshes
-- ------------------------------------------------------------

ALTER TABLE v3_location_change_history
    DROP CONSTRAINT IF EXISTS fk_v3_change_location;

-- Historical location IDs must survive even when the current
-- v3_business_locations snapshot is refreshed.