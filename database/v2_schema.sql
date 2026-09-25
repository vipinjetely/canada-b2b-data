-- Canada B2B Data Automation System - V2
-- Multi-source, freshness-aware, provenance-aware schema

CREATE TABLE IF NOT EXISTS data_sources (
    id BIGSERIAL PRIMARY KEY,

    source_key TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,

    jurisdiction TEXT,
    source_url TEXT,

    update_frequency TEXT,
    licence_name TEXT,
    commercial_use_allowed BOOLEAN,

    last_source_update_at TIMESTAMPTZ,
    last_collected_at TIMESTAMPTZ,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS business_entities (
    id BIGSERIAL PRIMARY KEY,

    legal_name TEXT NOT NULL,
    operating_name TEXT,

    federal_corporation_number TEXT,
    business_number TEXT,

    province_registry_id TEXT,
    registry_jurisdiction TEXT,

    status TEXT,
    incorporation_date DATE,

    street TEXT,
    street_2 TEXT,
    city TEXT,
    province VARCHAR(10),
    country VARCHAR(10) DEFAULT 'CA',
    postal_code VARCHAR(20),

    website TEXT,
    phone TEXT,
    email TEXT,

    industry TEXT,
    naics_code TEXT,

    employee_count INTEGER,
    employee_size_bucket TEXT,

    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ,

    quality_score NUMERIC(5,2),
    confidence_score NUMERIC(5,2),

    do_not_call BOOLEAN NOT NULL DEFAULT FALSE,

    is_new_1d BOOLEAN NOT NULL DEFAULT FALSE,
    is_new_7d BOOLEAN NOT NULL DEFAULT FALSE,
    is_new_30d BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS business_source_records (
    id BIGSERIAL PRIMARY KEY,

    business_id BIGINT NOT NULL
        REFERENCES business_entities(id)
        ON DELETE CASCADE,

    source_id BIGINT NOT NULL
        REFERENCES data_sources(id),

    source_record_id TEXT NOT NULL,

    source_business_name TEXT,
    source_status TEXT,

    source_updated_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_verified_at TIMESTAMPTZ,

    raw_record JSONB,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (source_id, source_record_id)
);


CREATE TABLE IF NOT EXISTS field_provenance (
    id BIGSERIAL PRIMARY KEY,

    business_id BIGINT NOT NULL
        REFERENCES business_entities(id)
        ON DELETE CASCADE,

    source_record_id BIGINT NOT NULL
        REFERENCES business_source_records(id)
        ON DELETE CASCADE,

    field_name TEXT NOT NULL,
    field_value TEXT,

    confidence_score NUMERIC(5,2),

    observed_at TIMESTAMPTZ,
    verified_at TIMESTAMPTZ,

    is_selected_value BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (business_id, source_record_id, field_name)
);


CREATE TABLE IF NOT EXISTS business_contacts (
    id BIGSERIAL PRIMARY KEY,

    business_id BIGINT NOT NULL
        REFERENCES business_entities(id)
        ON DELETE CASCADE,

    full_name TEXT,
    job_title TEXT,
    contact_role TEXT,

    email TEXT,
    phone TEXT,

    source_id BIGINT
        REFERENCES data_sources(id),

    source_url TEXT,

    last_verified_at TIMESTAMPTZ,
    confidence_score NUMERIC(5,2),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS business_change_history (
    id BIGSERIAL PRIMARY KEY,

    business_id BIGINT NOT NULL
        REFERENCES business_entities(id)
        ON DELETE CASCADE,

    field_name TEXT NOT NULL,

    old_value TEXT,
    new_value TEXT,

    source_id BIGINT
        REFERENCES data_sources(id),

    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS pipeline_runs (
    id BIGSERIAL PRIMARY KEY,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,

    status TEXT NOT NULL,

    records_collected BIGINT DEFAULT 0,
    records_inserted BIGINT DEFAULT 0,
    records_updated BIGINT DEFAULT 0,
    records_deduplicated BIGINT DEFAULT 0,
    records_failed BIGINT DEFAULT 0,

    error_message TEXT
);


CREATE INDEX IF NOT EXISTS idx_business_entities_legal_name
    ON business_entities (legal_name);

CREATE INDEX IF NOT EXISTS idx_business_entities_operating_name
    ON business_entities (operating_name);

CREATE INDEX IF NOT EXISTS idx_business_entities_federal_number
    ON business_entities (federal_corporation_number);

CREATE INDEX IF NOT EXISTS idx_business_entities_business_number
    ON business_entities (business_number);

CREATE INDEX IF NOT EXISTS idx_business_entities_province_registry
    ON business_entities (registry_jurisdiction, province_registry_id);

CREATE INDEX IF NOT EXISTS idx_business_entities_province
    ON business_entities (province);

CREATE INDEX IF NOT EXISTS idx_business_entities_city
    ON business_entities (city);

CREATE INDEX IF NOT EXISTS idx_business_entities_postal
    ON business_entities (postal_code);

CREATE INDEX IF NOT EXISTS idx_business_entities_naics
    ON business_entities (naics_code);

CREATE INDEX IF NOT EXISTS idx_business_entities_employee_bucket
    ON business_entities (employee_size_bucket);

CREATE INDEX IF NOT EXISTS idx_business_entities_last_seen
    ON business_entities (last_seen_at);

CREATE INDEX IF NOT EXISTS idx_business_source_records_business
    ON business_source_records (business_id);

CREATE INDEX IF NOT EXISTS idx_business_source_records_source
    ON business_source_records (source_id);

CREATE INDEX IF NOT EXISTS idx_field_provenance_business
    ON field_provenance (business_id);

CREATE INDEX IF NOT EXISTS idx_business_contacts_business
    ON business_contacts (business_id);

CREATE INDEX IF NOT EXISTS idx_change_history_business
    ON business_change_history (business_id);

CREATE INDEX IF NOT EXISTS idx_change_history_detected
    ON business_change_history (detected_at);