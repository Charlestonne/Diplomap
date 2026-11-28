-- Load fact_visit from resolved staging rows.
-- (NB : currently GDELT events remain empty until the GDELT staging pipeline is available)

INSERT INTO fact_visit (
    visit_key,
    leader_key,
    visitor_country_key,
    host_country_key,
    start_date_key,
    end_date_key,
    duration_days,
    is_multilateral,
    matched_in_gdelt,
    wiki_page_id,
    wiki_revision_id,
    pre_window_start,
    pre_window_end,
    post_window_start,
    post_window_end
)
SELECT row_number() OVER (
           ORDER BY visit.wiki_page_id,
                    visit.wiki_revision_id,
                    visit.source_table_index,
                    visit.source_row_index
       )::BIGINT,
       leader.leader_key,
       visitor.country_key,
       host.country_key,
       visit.start_date,
       visit.end_date,
       visit.duration_days,
       visit.is_multilateral,
       false,
       visit.wiki_page_id,
       visit.wiki_revision_id,
       visit.start_date - getvariable('analysis_window_days')::INTEGER,
       visit.start_date - 1,
       visit.end_date + 1,
       visit.end_date + getvariable('analysis_window_days')::INTEGER
FROM stg_visit AS visit
JOIN dim_leader AS leader
  ON leader.leader_id = visit.leader_qid
 AND leader.valid_from <= visit.start_date
 AND (leader.valid_to IS NULL OR leader.valid_to >= visit.start_date)
JOIN dim_country AS visitor
  ON visitor.iso3_code = visit.visitor_country_iso3
JOIN dim_country AS host
  ON host.iso3_code = visit.host_country_iso3;
