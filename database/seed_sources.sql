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
    'corporations_canada',
    'Corporations Canada - Federal Corporations',
    'government_registry',
    'Federal',
    'https://open.canada.ca/data/en/dataset/0032ce54-c5dd-4b66-99a0-320a7b5e99f2',
    'daily',
    'Open Government Licence - Canada',
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
    is_active = EXCLUDED.is_active,
    updated_at = NOW();