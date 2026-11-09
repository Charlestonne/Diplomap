"""Tests for the serving views v_visit_event and v_kpi_visit (warehouse/views/) on a hand-computed set.

Run from the repository root:

    pytest warehouse/tests/test_serving_views.py

Requires: duckdb, pytest, pyyaml.

France (1) visits Japan (2) twice, 2025-03-10..12 and 2025-03-20..21, so the POST window of visit 1
(03-13..03-27) overlaps both the visit days and the PRE window of visit 2 (03-05..03-19).
Visit 3 is a multilateral France -> Germany (3) visit. Visit 4 (France -> Italy, June) has no event.
"""

from pathlib import Path

import duckdb
import pytest
import yaml

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
     DATE '2025-04-25', DATE '2025-05-09', DATE '2025-05-11', DATE '2025-05-25'),
    (4, 1, 1, 4, 1, DATE '2025-06-10', DATE '2025-06-10', 1, FALSE, FALSE, 1, 1,
     DATE '2025-05-26', DATE '2025-06-09', DATE '2025-06-11', DATE '2025-06-25');
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


# Computed by hand from the events above:
#   visit 1  PRE {101}       POST {104, 105}
#   visit 2  PRE {103, 104}  POST {105}
#   visit 3  PRE {}          POST {107}
#   visit 4  no event
# Columns: visit, n_pre, n_post, coop_pre, coop_post, d_coop, tone_pre, tone_post, d_tone,
#          goldstein_pre, goldstein_post, d_goldstein, is_low_volume, has_overlap
EXPECTED_KPI = [
    (1, 1, 2, 1.0, 0.5, -0.5, 2.0, 0.0, -2.0, 1.0, -2.0, -3.0, True, True),
    (2, 2, 1, 0.5, 0.0, -0.5, -1.0, -1.0, 0.0, -2.0, -5.0, -3.0, True, True),
    (3, 0, 1, None, 1.0, None, None, 1.0, None, None, 1.0, None, True, False),
    (4, 0, 0, None, None, None, None, None, None, None, None, None, True, False),
]


def build():
    connection = duckdb.connect()
    connection.execute((ROOT / "warehouse" / "dimensions_and_facts" / "schema.sql").read_text())
    connection.execute(SEED)
    for view in ("v_visit_event", "v_kpi_visit"):
        connection.execute((ROOT / "warehouse" / "views" / f"{view}.sql").read_text())
    return connection


def test_attribution_matches_the_hand_computation():
    connection = build()
    rows = connection.execute(
        "SELECT visit_key, gdelt_event_id, visit_window, day_offset FROM v_visit_event ORDER BY 1, 2"
    ).fetchall()
    assert rows == EXPECTED
    # One row per (visit, event).
    assert connection.execute(
        "SELECT count(*) = count(DISTINCT (visit_key, gdelt_event_id)) FROM v_visit_event"
    ).fetchone()[0]


def test_kpi_match_the_hand_computation():
    rows = build().execute("SELECT * FROM v_kpi_visit ORDER BY visit_key").fetchall()
    assert rows == EXPECTED_KPI


@pytest.mark.parametrize("view", ["v_visit_event", "v_kpi_visit"])
def test_view_matches_its_contract(view):
    """Names, order and types (a view reports every column as nullable, so nullability is not checked)."""
    actual = build().execute(
        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = ? ORDER BY ordinal_position",
        [view],
    ).fetchall()
    contract = yaml.safe_load((ROOT / "table_contracts" / f"{view}.yml").read_text())
    assert actual == [(c["name"], c["type"]) for c in contract["columns"]]
