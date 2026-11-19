-- This script will build and load the production dimensions, including the country reference data.
-- Load production dimensions from the current staging snapshot

INSERT INTO dim_country (country_key, country_name, iso3_code, fips_code, cameo_code, region)
SELECT row_number() OVER (ORDER BY reference.iso3_code)::INTEGER,
       reference.country_name,
       reference.iso3_code,
       collected.fips_code,
       reference.cameo_code,
       reference.region
FROM stg_country_reference AS reference
LEFT JOIN (
    SELECT iso3_code, max(fips_code) AS fips_code
    FROM stg_country
    GROUP BY iso3_code
) AS collected ON collected.iso3_code = reference.iso3_code;

INSERT INTO dim_date (date_key, year, month, week, day)
WITH calendar AS (
    SELECT date_value::DATE AS date_key
    FROM generate_series(
        getvariable('analysis_start_date')::DATE - getvariable('analysis_window_days')::INTEGER,
        getvariable('analysis_end_date')::DATE + getvariable('analysis_window_days')::INTEGER,
        INTERVAL 1 DAY
    ) AS generated(date_value)
)
SELECT date_key, year(date_key), month(date_key), week(date_key), day(date_key)
FROM calendar;
INSERT INTO dim_leader (
    leader_key,
    leader_id,
    leader_name,
    position_title,
    represented_country_key,
    valid_from,
    valid_to
)
SELECT row_number() OVER (ORDER BY office.leader_qid, office.valid_from)::INTEGER,
       office.leader_qid,
       office.leader_name,
       office.position_title,
       country.country_key,
       office.valid_from,
       office.valid_to
FROM stg_leader AS office
JOIN dim_country AS country
  ON country.iso3_code = office.represented_country_iso3;
