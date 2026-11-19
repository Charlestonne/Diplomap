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
