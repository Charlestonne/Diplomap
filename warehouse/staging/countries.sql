-- Prepare stg_country candidates without inserting or discarding any source row.
-- Contract: table_contracts/stg_country.yml.

CREATE OR REPLACE TEMP TABLE country_candidates AS
SELECT
    json ->> '$.country_qid' AS country_qid,
    json ->> '$.country_name' AS country_name,
    json ->> '$.iso3_code' AS iso3_code,
    json ->> '$.fips_code' AS fips_code,
    json ->> '$.reference_status' AS reference_status,
    json AS source_record
FROM read_json_objects(getvariable('countries_file'), format = 'array');
