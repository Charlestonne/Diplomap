-- v_visit: one row per visit, with its keys resolved to readable values (routes /visits and /visits/{visit_key}).
-- The leader columns come from the dim_leader version valid on the start date (fact_visit.leader_key), so
-- leader_name and position_title are those of the office held during the visit.
-- Inner joins are safe: every key of fact_visit is NOT NULL and a foreign key.

CREATE OR REPLACE VIEW v_visit AS
SELECT v.visit_key,
       l.leader_id,
       l.leader_name,
       l.position_title,
       cv.iso3_code          AS visitor_iso3,
       cv.country_name       AS visitor_country_name,
       ch.iso3_code          AS host_iso3,
       ch.country_name       AS host_country_name,
       t.visit_type_label,
       v.start_date_key      AS start_date,
       v.end_date_key        AS end_date,
       v.duration_days,
       v.is_multilateral,
       v.matched_in_gdelt,
       v.pre_window_start,
       v.pre_window_end,
       v.post_window_start,
       v.post_window_end,
       v.wiki_page_id,
       v.wiki_revision_id
FROM fact_visit v
JOIN dim_leader     l  ON l.leader_key      = v.leader_key
JOIN dim_country    cv ON cv.country_key    = v.visitor_country_key
JOIN dim_country    ch ON ch.country_key    = v.host_country_key
JOIN dim_visit_type t  ON t.visit_type_key  = v.visit_type_key;
