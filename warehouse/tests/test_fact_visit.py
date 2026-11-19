"""Tests for the load of fact_visit (warehouse/dimensions_and_facts/build_facts.py).

Run from the repository root:

    pytest warehouse/tests/test_fact_visit.py

Requires: duckdb, pytest.

Leader Q1 holds two offices (two dim_leader versions, the second for another country). Each visit must point
to the version valid on its first day, take its visitor country from that version, and be matched in GDELT
only by a 042/043 event of the same pair during the visit. One broken visit per P4 rule must be quarantined.
"""

import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "warehouse" / "dimensions_and_facts"))
import build_facts  # noqa: E402

SEED = """
INSERT INTO dim_country (country_key, country_name, iso3_code, fips_code, cameo_code, region) VALUES
    (1, 'France', 'FRA', 'FR', 'FRA', 'Europe'), (2, 'Japan', 'JPN', 'JA', 'JPN', 'Asia'),
    (3, 'Germany', 'DEU', 'GM', 'DEU', 'Europe');
INSERT INTO dim_visit_type VALUES (1, 'state'), (2, 'unknown');
INSERT INTO dim_date
SELECT CAST(d AS DATE), year(d), month(d), week(d), day(d)
FROM generate_series(DATE '2024-12-17', DATE '2025-07-15', INTERVAL 1 DAY) AS t(d);
-- Q1: President of France until 2025-03-31, then Chancellor of Germany.
INSERT INTO dim_leader VALUES
    (10, 'Q1', 'Leader A', 'President',  1, DATE '2020-01-01', DATE '2025-03-31'),
    (11, 'Q1', 'Leader A', 'Chancellor', 3, DATE '2025-04-01', NULL);
CREATE TABLE stg_gdelt_event (event_date DATE, actor1_country_code VARCHAR, actor2_country_code VARCHAR,
                              event_code VARCHAR);
INSERT INTO stg_gdelt_event VALUES
    (DATE '2025-03-31', 'JPN', 'FRA', '043'),   -- matches visit 2 (reversed pair, last day)
    (DATE '2025-04-03', 'DEU', 'JPN', '040'),   -- not a visit code
    (DATE '2025-04-05', 'DEU', 'JPN', '042');   -- the day after visit 3
CREATE TABLE stg_visit (leader_id VARCHAR, host_country_iso3 VARCHAR, start_date DATE, end_date DATE,
                        visit_type_label VARCHAR, is_multilateral BOOLEAN,
                        wiki_page_id BIGINT, wiki_revision_id BIGINT);
INSERT INTO stg_visit VALUES
    -- valid
    ('Q1', 'JPN', DATE '2025-02-10', DATE '2025-02-12', 'state',    FALSE, 100, 1),
    ('Q1', 'JPN', DATE '2025-03-31', DATE '2025-04-01', 'official', FALSE, 100, 1),  -- last day of version 10
    ('Q1', 'JPN', DATE '2025-04-01', DATE '2025-04-04', 'state',    TRUE,  100, 2),  -- first day of version 11
    -- one broken row per rule
    ('Q9', 'JPN', DATE '2025-02-10', DATE '2025-02-11', 'state', FALSE, 100, 1),     -- visit_01
    ('Q1', 'XXX', DATE '2025-02-10', DATE '2025-02-11', 'state', FALSE, 100, 1),     -- visit_02
    ('Q1', 'FRA', DATE '2025-02-10', DATE '2025-02-11', 'state', FALSE, 100, 1),     -- visit_03
    ('Q1', 'DEU', DATE '2025-02-12', DATE '2025-02-10', 'state', FALSE, 100, 1),     -- visit_04
    ('Q1', 'JPN', DATE '2025-06-29', DATE '2025-07-20', 'state', FALSE, 100, 1),     -- visit_05
    ('Q1', 'DEU', DATE '2025-01-20', DATE '2025-01-21', 'state', NULL,  100, 1),     -- visit_06
    ('Q1', 'JPN', DATE '2025-02-10', DATE '2025-02-12', 'state', FALSE, 100, 0);     -- visit_07 (older revision)
"""


def build():
    connection = duckdb.connect()
    connection.execute((ROOT / "warehouse" / "dimensions_and_facts" / "schema.sql").read_text())
    connection.execute(SEED)
    build_facts.build_fact_visit(connection)
    return connection


def test_each_visit_points_to_the_leader_version_valid_on_its_first_day():
    rows = build().execute(
        """
        SELECT visit_key, start_date_key::VARCHAR, leader_key, visitor_country_key, visit_type_key,
               duration_days, matched_in_gdelt, pre_window_start::VARCHAR, post_window_end::VARCHAR
        FROM fact_visit ORDER BY visit_key
        """
    ).fetchall()
    assert rows == [
        (1, "2025-02-10", 10, 1, 1, 3, False, "2025-01-26", "2025-02-27"),
        (2, "2025-03-31", 10, 1, 2, 2, True,  "2025-03-16", "2025-04-16"),
        (3, "2025-04-01", 11, 3, 1, 4, False, "2025-03-17", "2025-04-19"),
    ]


def test_each_broken_visit_is_quarantined_under_its_rule():
    connection = build()
    quarantined = dict(connection.execute(
        "SELECT rule_id, count(*) FROM quality_quarantine GROUP BY 1").fetchall())
    assert quarantined == {f"visit_0{i}_{name}": 1 for i, name in enumerate(
        ["leader_unknown", "host_unknown", "same_country", "dates_invalid", "out_of_scope",
         "field_missing", "duplicate"], start=1)}
    # The duplicate kept is the latest revision.
    assert connection.execute(
        "SELECT row_data->>'wiki_revision_id' FROM quality_quarantine WHERE rule_id = 'visit_07_duplicate'"
    ).fetchone()[0] == "0"


def test_rebuild_gives_the_same_table():
    connection = build()
    before = connection.execute("SELECT * FROM fact_visit ORDER BY visit_key").fetchall()
    build_facts.build_fact_visit(connection)
    assert connection.execute("SELECT * FROM fact_visit ORDER BY visit_key").fetchall() == before
