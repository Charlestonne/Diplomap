"""Tests for v_visit_event (warehouse/views/v_visit_event.sql) on a hand-computed set.

Run from the repository root:

    pytest warehouse/tests/test_v_visit_event.py

Requires: duckdb, pytest.

France (1) visits Japan (2) twice, 2025-03-10..12 and 2025-03-20..21, so the POST window of visit 1
(03-13..03-27) overlaps both the visit days and the PRE window of visit 2 (03-05..03-19).
Visit 3 is a multilateral France -> Germany (3) visit.
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]

SEED = """
INSERT INTO dim_country (country_key, country_name, iso3_code, fips_code, cameo_code, region) VALUES
    (1, 'France', 'FRA', 'FR', 'FRA', NULL), (2, 'Japan', 'JPN', 'JA', 'JPN', NULL),
    (3, 'Germany', 'DEU', 'GM', 'DEU', NULL), (4, 'Italy', 'ITA', 'IT', 'ITA', NULL);
INSERT INTO dim_visit_type VALUES (1, 'state');
INSERT INTO dim_event_type VALUES (1, '042', '04', 1, TRUE), (2, '190', '19', 4, FALSE);
INSERT INTO dim_leader VALUES (1, 'Q1', 'Leader A', NULL, 1, DATE '2020-01-01', NULL);
INSERT INTO dim_date
SELECT CAST(d AS DATE), year(d), month(d), week(d), day(d)
FROM generate_series(DATE '2024-12-17', DATE '2025-07-15', INTERVAL 1 DAY) AS t(d);
INSERT INTO fact_visit VALUES
    (1, 1, 1, 2, 1, DATE '2025-03-10', DATE '2025-03-12', 3, FALSE, FALSE, 1, 1,
     DATE '2025-02-23', DATE '2025-03-09', DATE '2025-03-13', DATE '2025-03-27'),
    (2, 1, 1, 2, 1, DATE '2025-03-20', DATE '2025-03-21', 2, FALSE, FALSE, 1, 1,
     DATE '2025-03-05', DATE '2025-03-19', DATE '2025-03-22', DATE '2025-04-05'),
    (3, 1, 1, 3, 1, DATE '2025-05-10', DATE '2025-05-10', 1, TRUE, FALSE, 1, 1,
     DATE '2025-04-25', DATE '2025-05-09', DATE '2025-05-11', DATE '2025-05-25');
INSERT INTO fact_gdelt_event VALUES
    (101, DATE '2025-02-23', 1, 2, 1, 'u101', 1.0, 2.0, 3),   -- first day of PRE of visit 1
    (102, DATE '2025-02-22', 1, 2, 1, 'u102', 1.0, 2.0, 3),   -- one day too early
    (103, DATE '2025-03-11', 2, 1, 2, 'u103', -5.0, -3.0, 2), -- during visit 1: no window (and PRE of visit 2)
    (104, DATE '2025-03-15', 2, 1, 1, 'u104', 1.0, 1.0, 2),   -- POST of 1 and PRE of 2, reversed pair
    (105, DATE '2025-03-27', 1, 2, 2, 'u105', -5.0, -1.0, 2), -- last day of POST of 1, POST of 2
    (106, DATE '2025-03-15', 1, 4, 1, 'u106', 1.0, 1.0, 2),   -- France-Italy: not the pair
    (107, DATE '2025-05-12', 3, 1, 1, 'u107', 1.0, 1.0, 2),   -- POST of multilateral visit 3
    (108, DATE '2025-05-12', 3, 4, 1, 'u108', 1.0, 1.0, 2);   -- Germany-Italy: another participant, not kept
"""

# Computed by hand: (visit_key, gdelt_event_id, window, day_offset)
EXPECTED = [
    (1, 101, "PRE", -15),
    (1, 104, "POST", 3),
    (1, 105, "POST", 15),
    (2, 103, "PRE", -9),
    (2, 104, "PRE", -5),
    (2, 105, "POST", 6),
    (3, 107, "POST", 2),
]


def test_attribution_matches_the_hand_computation():
    connection = duckdb.connect()
    connection.execute((ROOT / "warehouse" / "dimensions_and_facts" / "schema.sql").read_text())
    connection.execute(SEED)
    connection.execute((ROOT / "warehouse" / "views" / "v_visit_event.sql").read_text())
    rows = connection.execute(
        "SELECT visit_key, gdelt_event_id, visit_window, day_offset FROM v_visit_event ORDER BY 1, 2"
    ).fetchall()
    assert rows == EXPECTED
    # One row per (visit, event).
    assert connection.execute(
        "SELECT count(*) = count(DISTINCT (visit_key, gdelt_event_id)) FROM v_visit_event"
    ).fetchone()[0]
