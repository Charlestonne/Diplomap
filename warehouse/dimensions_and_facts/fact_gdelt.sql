-- stg_gdelt_event + conformed dimensions -> candidate rows for fact_gdelt_event.
-- Missing dimension keys remain NULL so the quality gate can quarantine them
-- with an explicit reason instead of silently dropping the event.

CREATE OR REPLACE TABLE stg_fact_gdelt AS
SELECT e.gdelt_event_id,
       e.event_date                                      AS event_date_key,
       d.date_key                                        AS resolved_date_key,
       c1.country_key                                    AS actor1_country_key,
       c2.country_key                                    AS actor2_country_key,
       t.event_type_key,
       e.source_url,
       e.goldstein_scale,
       e.avg_tone,
       e.num_mentions
FROM stg_gdelt_event e
LEFT JOIN dim_date d
       ON d.date_key = e.event_date
LEFT JOIN dim_country c1
       ON c1.cameo_code = e.actor1_country_code
LEFT JOIN dim_country c2
       ON c2.cameo_code = e.actor2_country_code
LEFT JOIN dim_event_type t
       ON t.cameo_code = e.event_code;
