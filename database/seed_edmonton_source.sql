INSERT INTO data_sources (
    source_key,
    source_name,
    source_type,
    jurisdiction,
    source_url,
    update_frequency,
    licence_name,
    commercial_use_allowed,
    is_active
)
VALUES (
    'edmonton_business_licences',
    'City of Edmonton Business Licences',
    'municipal_business_licence',
    'Edmonton, AB',
    'https://data.edmonton.ca/resource/qhi4-bdpu.json',
    'daily',
    'Open Government Licence - Edmonton',
    TRUE,
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