CREATE TABLE IF NOT EXISTS businesses (
    id BIGSERIAL PRIMARY KEY,

    corporation_number TEXT NOT NULL UNIQUE,
    business_number TEXT,

    business_name TEXT NOT NULL,
    business_name_alt TEXT,

    governing_legislation TEXT,
    status TEXT,
    status_detail TEXT,

    anniversary_date DATE,
    last_annual_filing_year INTEGER,
    last_annual_meeting_date DATE,

    street TEXT,
    street_2 TEXT,
    city TEXT,
    province VARCHAR(10),
    country VARCHAR(10),
    postal_code VARCHAR(20),

    minimum_directors INTEGER,
    maximum_directors INTEGER,

    odbus_business_sector TEXT,
    odbus_business_subsector TEXT,
    odbus_business_description TEXT,
    odbus_derived_naics TEXT,
    odbus_source_naics_primary TEXT,
    odbus_naics_description TEXT,

    odbus_latitude DOUBLE PRECISION,
    odbus_longitude DOUBLE PRECISION,
    odbus_total_employees TEXT,
    odbus_provider TEXT,
    odbus_source_record_id TEXT,

    odbus_matched BOOLEAN NOT NULL DEFAULT FALSE,

    source TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    collected_at_utc TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_businesses_name
    ON businesses (business_name);

CREATE INDEX IF NOT EXISTS idx_businesses_province
    ON businesses (province);

CREATE INDEX IF NOT EXISTS idx_businesses_postal_code
    ON businesses (postal_code);

CREATE INDEX IF NOT EXISTS idx_businesses_business_number
    ON businesses (business_number);

CREATE INDEX IF NOT EXISTS idx_businesses_odbus_naics
    ON businesses (odbus_derived_naics);