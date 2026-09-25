INSERT INTO data_sources (
    source_key,
    source_name,
    source_type,
    jurisdiction,
    source_url,
    update_frequency,
    licence,
    commercial_use_allowed,
    is_active
)
VALUES (
    'calgary_business_licences',
    'City of Calgary Business Licences',
    'municipal_business_licence',
    'Calgary, AB',
    'https://data.calgary.ca/resource/vdjc-pybd.json',
    'daily',
    'Open Government Licence - City of Calgary',
    TRUE,
    TRUE
)
ON CONFLICT (source_key)
DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_type = EXCLUDED.source_type,
    jurisdiction = EXCLUDED.jurisdiction,
    source_url = EXCLUDED.source_url,
    update_frequency = EXCLUDED.update_frequency,
    licence = EXCLUDED.licence,
    commercial_use_allowed = EXCLUDED.commercial_use_allowed,
    is_active = EXCLUDED.is_active;