-- Idempotent production dimension load.
-- The source files are mounted at /opt/diplomap/DB in the Airflow image.

CREATE OR REPLACE TEMP TABLE dim_country_source AS
SELECT row_number() OVER (ORDER BY code)::INTEGER AS country_key,
       label AS country_name,
       code AS iso3_code,
       NULL::VARCHAR AS fips_code,
       code AS cameo_code,
       NULL::VARCHAR AS region
FROM read_csv(
    '/opt/diplomap/DB/CAMEO.country.txt',
    delim = '\t',
    header = true,
    columns = {'CODE': 'VARCHAR', 'LABEL': 'VARCHAR'}
)
WHERE code NOT IN (
    'WSB', 'BAG', 'GZS', 'AFR', 'ASA', 'BLK', 'CRB', 'CAU', 'CFR', 'CAS',
    'CEU', 'EIN', 'EAF', 'EEU', 'EUR', 'LAM', 'MEA', 'MDT', 'NAF', 'NMR',
    'PGS', 'SCN', 'SAM', 'SAS', 'SEA', 'SAF', 'WAF', 'WST'
);

UPDATE dim_country AS target
SET country_name = source.country_name,
    iso3_code = source.iso3_code,
    fips_code = source.fips_code,
    region = source.region
FROM dim_country_source AS source
WHERE target.cameo_code = source.cameo_code;

INSERT INTO dim_country
SELECT source.country_key, source.country_name, source.iso3_code,
       source.fips_code, source.cameo_code, source.region
FROM dim_country_source AS source
WHERE NOT EXISTS (
    SELECT 1 FROM dim_country AS target
    WHERE target.cameo_code = source.cameo_code
);

CREATE OR REPLACE TEMP TABLE dim_event_type_source AS
SELECT row_number() OVER (ORDER BY CAST(CAMEOEVENTCODE AS INTEGER))::INTEGER AS event_type_key,
       CAMEOEVENTCODE AS cameo_code,
       left(CAMEOEVENTCODE, 2) AS root_code,
       CASE
           WHEN CAST(left(CAMEOEVENTCODE, 2) AS INTEGER) BETWEEN 1 AND 5 THEN 1
           WHEN CAST(left(CAMEOEVENTCODE, 2) AS INTEGER) BETWEEN 6 AND 9 THEN 2
           WHEN CAST(left(CAMEOEVENTCODE, 2) AS INTEGER) BETWEEN 10 AND 14 THEN 3
           ELSE 4
       END AS quad_class,
       CAST(
           CASE
               WHEN CAST(left(CAMEOEVENTCODE, 2) AS INTEGER) BETWEEN 1 AND 9 THEN true
               ELSE false
           END AS BOOLEAN
       ) AS is_cooperative
FROM read_csv(
    '/opt/diplomap/DB/CAMEO.eventcodes.txt',
    delim = '\t',
    header = true,
    columns = {'CAMEOEVENTCODE': 'VARCHAR', 'EVENTDESCRIPTION': 'VARCHAR'}
)
WHERE regexp_full_match(CAMEOEVENTCODE, '[0-9]{2,4}');

UPDATE dim_event_type AS target
SET root_code = source.root_code,
    quad_class = source.quad_class,
    is_cooperative = source.is_cooperative
FROM dim_event_type_source AS source
WHERE target.cameo_code = source.cameo_code;

INSERT INTO dim_event_type
SELECT source.event_type_key, source.cameo_code, source.root_code,
       source.quad_class, source.is_cooperative
FROM dim_event_type_source AS source
WHERE NOT EXISTS (
    SELECT 1 FROM dim_event_type AS target
    WHERE target.cameo_code = source.cameo_code
);

INSERT INTO dim_date (date_key, year, month, week, day)
SELECT CAST(value AS DATE), year(CAST(value AS DATE)), month(CAST(value AS DATE)),
       week(CAST(value AS DATE)), day(CAST(value AS DATE))
FROM generate_series(
    DATE '2024-12-17',
    DATE '2025-07-15',
    INTERVAL 1 DAY
) AS dates(value)
WHERE NOT EXISTS (
    SELECT 1 FROM dim_date AS target
    WHERE target.date_key = CAST(dates.value AS DATE)
);
