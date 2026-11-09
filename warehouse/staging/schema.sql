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

CREATE TABLE IF NOT EXISTS stg_leader (
    collection_id VARCHAR NOT NULL,
    statement_uri VARCHAR NOT NULL,
    leader_local_id VARCHAR NOT NULL,
    leader_qid VARCHAR NOT NULL,
    leader_name VARCHAR NOT NULL,
    position_qid VARCHAR NOT NULL,
    position_title VARCHAR,
    represented_country_iso3 VARCHAR NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    end_date_status VARCHAR NOT NULL,
    source_file VARCHAR NOT NULL,
    source_record JSON NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (collection_id, statement_uri),

    CHECK (trim(collection_id) <> ''),
    CHECK (trim(leader_local_id) <> ''),
    CHECK (trim(leader_name) <> ''),
    CHECK (trim(source_file) <> ''),
    CHECK (regexp_full_match(statement_uri, 'https?://www[.]wikidata[.]org/entity/statement/.+')),
    CHECK (regexp_full_match(leader_qid, 'Q[1-9][0-9]*')),
    CHECK (regexp_full_match(position_qid, 'Q[1-9][0-9]*')),
    CHECK (regexp_full_match(represented_country_iso3, '[A-Z]{3}')),
    CHECK (valid_to IS NULL OR valid_to >= valid_from),
    CHECK (
        (valid_to IS NULL AND end_date_status = 'not_reported_open_interval')
        OR (valid_to IS NOT NULL AND end_date_status = 'reported')
    )
);
