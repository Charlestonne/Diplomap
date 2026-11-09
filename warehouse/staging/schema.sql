-- Create the staging tables before running their load scripts.
-- Contracts: table_contracts/stg_country.yml, stg_leader.yml, stg_visit.yml.

CREATE TABLE IF NOT EXISTS stg_country (
    collection_id VARCHAR NOT NULL,
    country_qid VARCHAR NOT NULL,
    country_name VARCHAR NOT NULL,
    iso3_code VARCHAR NOT NULL,
    fips_code VARCHAR,
    source_file VARCHAR NOT NULL,
    source_record JSON NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (collection_id, country_qid),
    UNIQUE (collection_id, iso3_code),
    UNIQUE (collection_id, fips_code),

    CHECK (regexp_full_match(iso3_code, '[A-Z]{3}')),
    CHECK (regexp_full_match(country_qid, 'Q[1-9][0-9]*')),
    CHECK (fips_code IS NULL OR regexp_full_match(fips_code, '[A-Z]{2}'))

);
