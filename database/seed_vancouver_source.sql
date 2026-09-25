    INSERT INTO data_sources (
    source_key,
    source_name,
    source_type,
    jurisdiction,
    source_url,
    update_frequency,
    licence_name,
    commercial_use_allowed,
    last_collected_at,
    is_active
)
VALUES (
    'vancouver_business_licences',
    'City of Vancouver Business Licences',
    'municipal_business_licence',
    'Vancouver, BC',
    'https://opendata.vancouver.ca/explore/dataset/business-licences/',
    'daily',
    'Open Government Licence - Vancouver',
    TRUE,
    NULL,
    TRUE
)
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_type = EXCLUDED.source_type,
    jurisdiction = EXCLUDED.jurisdiction,
    source_url = EXCLUDED.source_url,
    update_frequency = EXCLUDED.update_frequency,
    licence_name = EXCLUDED.licence_name,
    commercial_use_allowed = EXCLUDED.commercial_use_allowed,
    is_active = TRUE,
    updated_at = NOW();