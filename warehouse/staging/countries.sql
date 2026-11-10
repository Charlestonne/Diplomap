-- Prepare and load countries, preserving rejected records in quarantine.
-- Contract: table_contracts/stg_country.yml.
-- Run through load_countries.py, which creates the schemas and owns the transaction.
-- Required session variables: countries_file and collection_id.

CREATE OR REPLACE TEMP TABLE country_candidates AS
SELECT
    ordinality AS source_row_index,
    json ->> '$.country_qid' AS country_qid,
    json ->> '$.country_name' AS country_name,
    json ->> '$.iso3_code' AS iso3_code,
    json ->> '$.fips_code' AS fips_code,
    json ->> '$.reference_status' AS reference_status,
    json AS source_record
FROM read_json_objects(getvariable('countries_file'), format = 'array') WITH ORDINALITY;

-- Store one row per problem in that table. A candidate can have several problems
CREATE OR REPLACE TEMP TABLE country_issues (
    source_row_index BIGINT NOT NULL,
    rejection_reason VARCHAR NOT NULL
);

-- 1. The previous resolution step must have marked the country as checked.
-- source_row_index is the one-based position assigned by WITH ORDINALITY when reading the JSON
INSERT INTO country_issues
SELECT source_row_index, 'country_not_checked'
FROM country_candidates
WHERE reference_status IS NULL OR reference_status <> 'checked';

-- 2. Require a valid Wikidata QID
INSERT INTO country_issues
SELECT source_row_index, 'invalid_country_qid'
FROM country_candidates
WHERE country_qid IS NULL OR NOT regexp_full_match(country_qid, 'Q[1-9][0-9]*');

-- 3. Require a nonempty name
INSERT INTO country_issues
SELECT source_row_index, 'missing_country_name'
FROM country_candidates
WHERE country_name IS NULL OR trim(country_name) = '';

-- 4. ISO3 is required and must contain exactly three uppercase letters
INSERT INTO country_issues
SELECT source_row_index, 'missing_or_invalid_iso3'
FROM country_candidates
WHERE iso3_code IS NULL OR NOT regexp_full_match(iso3_code, '[A-Z]{3}');

-- 5. FIPS may be NULL but a provided code must contain two uppercase letters
INSERT INTO country_issues
SELECT source_row_index, 'invalid_fips'
FROM country_candidates
WHERE fips_code IS NOT NULL AND NOT regexp_full_match(fips_code, '[A-Z]{2}');

-- 6. Flag every copy of a duplicated QID, rather than keeping an arbitrary row
INSERT INTO country_issues
SELECT source_row_index, 'duplicate_country_qid'
FROM country_candidates
WHERE country_qid IN (
    SELECT country_qid
    FROM country_candidates
    GROUP BY country_qid
    HAVING count(*) > 1
);

-- 7. An ISO3 code must not belong to several country QIDs
INSERT INTO country_issues
SELECT source_row_index, 'conflicting_iso3_code'
FROM country_candidates
WHERE iso3_code IN (
    SELECT iso3_code
    FROM country_candidates
    GROUP BY iso3_code
    HAVING count(DISTINCT country_qid) > 1
);

-- 8. The same uniqueness rule applies to non-NULL FIPS codes
INSERT INTO country_issues
SELECT source_row_index, 'conflicting_fips_code'
FROM country_candidates
WHERE fips_code IN (
    SELECT fips_code
    FROM country_candidates
    GROUP BY fips_code
    HAVING count(DISTINCT country_qid) > 1
);


-- Keep the full rejected record alongside each reason
-- NB : several rows here can describe different problems on the same candidate.
CREATE OR REPLACE TEMP TABLE rejected_countries AS
SELECT
    country.*,
    issue.rejection_reason
FROM country_candidates AS country
JOIN country_issues AS issue ON issue.source_row_index = country.source_row_index;

-- Accept a candidate only when no problem refers to its source row
CREATE OR REPLACE TEMP TABLE accepted_countries AS
SELECT country.*
FROM country_candidates AS country
WHERE NOT EXISTS (
    SELECT 1
    FROM country_issues AS issue
    WHERE issue.source_row_index = country.source_row_index
);

-- Replace only this collection's country results. The Python loader wraps both
-- deletion and insertion in one transaction, so failures preserve the old data.
DELETE FROM stg_country
WHERE collection_id = getvariable('collection_id');

DELETE FROM stg_quarantine
WHERE collection_id = getvariable('collection_id') AND target_table = 'stg_country';

INSERT INTO stg_country (
    collection_id, country_qid, country_name, iso3_code, fips_code,
    source_file, source_record
)
SELECT
    getvariable('collection_id'), country_qid, country_name, iso3_code, fips_code,
    getvariable('countries_file'), source_record
FROM accepted_countries;

INSERT INTO stg_quarantine (
    collection_id, target_table, source_row_index, rejection_reason,
    source_file, source_record
)
SELECT
    getvariable('collection_id'), 'stg_country', source_row_index,
    rejection_reason, getvariable('countries_file'), source_record
FROM rejected_countries;
