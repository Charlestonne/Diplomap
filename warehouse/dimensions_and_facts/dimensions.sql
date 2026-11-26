-- Idempotent dimension load (SCD1). Safe to rerun against a populated warehouse.
-- Only non-indexed columns are updated in place (country_name, region, ...), so DuckDB
-- never has to DELETE+INSERT a row that is referenced by a foreign key.
-- Indexed columns (country_key, iso3_code, fips_code, cameo_code) are never updated:
-- changing one of them for an existing member requires a controlled migration.
-- The source files are mounted at /opt/diplomap/DB in the Airflow image.
-- Excluded CAMEO entries: regions/groupings, ANT (no single current ISO-3166 mapping)
-- and the territories ALA, GUF, GLP, MTQ, NFK (not countries, absent from countrycode.csv).

CREATE OR REPLACE TEMP TABLE dim_country_source AS
WITH cameo AS (
    SELECT code AS cameo_code,
           label AS cameo_name,
           CASE code
               WHEN 'TMP' THEN 'TLS'
               WHEN 'IMY' THEN 'IMN'
               WHEN 'MTN' THEN 'MNE'
               WHEN 'ROM' THEN 'ROU'
               ELSE code
           END AS iso3_code
    FROM read_csv(
        '/opt/diplomap/DB/CAMEO.country.txt',
        delim = '\t',
        header = true,
        columns = {'CODE': 'VARCHAR', 'LABEL': 'VARCHAR'}
    )
    WHERE code NOT IN (
        'WSB', 'BAG', 'GZS', 'AFR', 'ASA', 'BLK', 'CRB', 'CAU', 'CFR', 'CAS',
        'CEU', 'EIN', 'EAF', 'EEU', 'EUR', 'LAM', 'MEA', 'MDT', 'NAF', 'NMR',
        'PGS', 'SCN', 'SAM', 'SAS', 'SEA', 'SAF', 'WAF', 'WST', 'ANT',
        'ALA', 'GUF', 'GLP', 'MTQ', 'NFK'
    )
),
iso AS (
    SELECT ISO3 AS iso3_code,
           FIPS AS fips_code,
           Continent AS region
    FROM read_csv(
        '/opt/diplomap/DB/countrycode.csv',
        delim = ',',
        header = true,
        columns = {
            'Country Name': 'VARCHAR',
            'ISO2': 'VARCHAR',
            'ISO3': 'VARCHAR',
            'Top Level Domain': 'VARCHAR',
            'FIPS': 'VARCHAR',
            'ISO Numeric': 'VARCHAR',
            'GeoNameID': 'VARCHAR',
            'E164': 'VARCHAR',
            'Phone Code': 'VARCHAR',
            'Continent': 'VARCHAR',
            'Capital': 'VARCHAR',
            'Time Zone in Capital': 'VARCHAR',
            'Currency': 'VARCHAR',
            'Language Codes': 'VARCHAR',
            'Languages': 'VARCHAR',
            'Area KM2': 'VARCHAR',
            'Internet Hosts': 'VARCHAR',
            'Internet Users': 'VARCHAR',
            'Phones (Mobile)': 'VARCHAR',
            'Phones (Landline)': 'VARCHAR',
            'GDP': 'VARCHAR'
        }
    )
)
SELECT cameo.cameo_name AS country_name,
       iso.iso3_code,
       iso.fips_code,
       cameo.cameo_code,
       iso.region
FROM cameo
JOIN iso ON iso.iso3_code = cameo.iso3_code;

-- SCD1: overwrite non-indexed attributes, only when they changed.
UPDATE dim_country AS target
SET country_name = source.country_name,
    region       = source.region
FROM dim_country_source AS source
WHERE target.cameo_code = source.cameo_code
  AND (target.country_name IS DISTINCT FROM source.country_name
    OR target.region       IS DISTINCT FROM source.region);

-- New members only: new surrogate keys, existing keys are never touched.
INSERT INTO dim_country (country_key, country_name, iso3_code, fips_code, cameo_code, region)
SELECT (SELECT coalesce(max(country_key), 0) FROM dim_country)::INTEGER
         + (row_number() OVER (ORDER BY source.cameo_code))::INTEGER,
       source.country_name, source.iso3_code, source.fips_code,
       source.cameo_code, source.region
FROM dim_country_source AS source
WHERE NOT EXISTS (
    SELECT 1 FROM dim_country AS target
    WHERE target.cameo_code = source.cameo_code
);

CREATE OR REPLACE TEMP TABLE dim_event_type_source AS
SELECT CAMEOEVENTCODE AS cameo_code,
       left(CAMEOEVENTCODE, 2) AS root_code,
       CASE
           WHEN CAST(left(CAMEOEVENTCODE, 2) AS INTEGER) BETWEEN 1 AND 5 THEN 1
           WHEN CAST(left(CAMEOEVENTCODE, 2) AS INTEGER) BETWEEN 6 AND 9 THEN 2
           WHEN CAST(left(CAMEOEVENTCODE, 2) AS INTEGER) BETWEEN 10 AND 14 THEN 3
           ELSE 4
       END AS quad_class,
       CAST(left(CAMEOEVENTCODE, 2) AS INTEGER) BETWEEN 1 AND 9 AS is_cooperative
FROM read_csv(
    '/opt/diplomap/DB/CAMEO.eventcodes.txt',
    delim = '\t',
    header = true,
    columns = {'CAMEOEVENTCODE': 'VARCHAR', 'EVENTDESCRIPTION': 'VARCHAR'}
)
WHERE regexp_full_match(CAMEOEVENTCODE, '[0-9]{2,4}');

UPDATE dim_event_type AS target
SET root_code      = source.root_code,
    quad_class     = source.quad_class,
    is_cooperative = source.is_cooperative
FROM dim_event_type_source AS source
WHERE target.cameo_code = source.cameo_code
  AND (target.root_code      IS DISTINCT FROM source.root_code
    OR target.quad_class     IS DISTINCT FROM source.quad_class
    OR target.is_cooperative IS DISTINCT FROM source.is_cooperative);

INSERT INTO dim_event_type (event_type_key, cameo_code, root_code, quad_class, is_cooperative)
SELECT (SELECT coalesce(max(event_type_key), 0) FROM dim_event_type)::INTEGER
         + (row_number() OVER (ORDER BY CAST(source.cameo_code AS INTEGER)))::INTEGER,
       source.cameo_code, source.root_code, source.quad_class, source.is_cooperative
FROM dim_event_type_source AS source
WHERE NOT EXISTS (
    SELECT 1 FROM dim_event_type AS target
    WHERE target.cameo_code = source.cameo_code
);

INSERT INTO dim_date (date_key, year, month, week, day)
SELECT CAST(value AS DATE), year(CAST(value AS DATE)), month(CAST(value AS DATE)),
       week(CAST(value AS DATE)), day(CAST(value AS DATE))
FROM generate_series(DATE '2024-12-17', DATE '2025-07-15', INTERVAL 1 DAY) AS dates(value)
WHERE NOT EXISTS (
    SELECT 1 FROM dim_date AS target
    WHERE target.date_key = CAST(dates.value AS DATE)
);
