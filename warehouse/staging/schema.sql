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

CREATE TABLE IF NOT EXISTS stg_visit (
    collection_id VARCHAR NOT NULL,
    leader_qid VARCHAR NOT NULL,
    office_statement_uri VARCHAR NOT NULL,
    visitor_country_qid VARCHAR NOT NULL,
    visitor_country_iso3 VARCHAR NOT NULL,
    host_country_qid VARCHAR NOT NULL,
    host_country_iso3 VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    duration_days INTEGER NOT NULL,
    is_multilateral BOOLEAN,
    is_transit BOOLEAN,
    wiki_language VARCHAR NOT NULL,
    wiki_page_id BIGINT NOT NULL,
    wiki_revision_id BIGINT NOT NULL,
    source_table_index INTEGER NOT NULL,
    source_row_index INTEGER NOT NULL,
    host_country_raw VARCHAR,
    date_raw VARCHAR,
    areas_visited_raw VARCHAR,
    details_raw VARCHAR,
    source_file VARCHAR NOT NULL,
    source_record JSON NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        collection_id, wiki_language, wiki_page_id, wiki_revision_id,
        source_table_index, source_row_index
    ),

    CHECK (trim(collection_id) <> ''),
    CHECK (trim(source_file) <> ''),
    CHECK (regexp_full_match(leader_qid, 'Q[1-9][0-9]*')),
    CHECK (regexp_full_match(office_statement_uri, 'https?://www[.]wikidata[.]org/entity/statement/.+')),
    CHECK (regexp_full_match(visitor_country_qid, 'Q[1-9][0-9]*')),
    CHECK (regexp_full_match(host_country_qid, 'Q[1-9][0-9]*')),
    CHECK (regexp_full_match(visitor_country_iso3, '[A-Z]{3}')),
    CHECK (regexp_full_match(host_country_iso3, '[A-Z]{3}')),
    CHECK (visitor_country_qid <> host_country_qid),
    CHECK (visitor_country_iso3 <> host_country_iso3),
    CHECK (end_date >= start_date),
    CHECK (duration_days >= 1 AND duration_days = end_date - start_date + 1),
    CHECK (wiki_language = 'en'),
    CHECK (wiki_page_id > 0 AND wiki_revision_id > 0),
    CHECK (source_table_index > 0 AND source_row_index > 0)
);
