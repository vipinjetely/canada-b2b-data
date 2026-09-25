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
    'toronto_business_licences',
    'City of Toronto Business Licences and Permits',
    'municipal_business_licence',
    'Toronto, ON',
    'https://open.toronto.ca/dataset/municipal-licensing-and-standards-business-licences-and-permits/',
    'daily',
    'Open Government Licence - Toronto',
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