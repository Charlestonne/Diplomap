from datetime import date

import pytest

from ingestion.wikipedia_trips.normalizer import normalize_visit, parse_visit_dates


@pytest.mark.parametrize('text,start,end', [
    ('9 January', '2025-01-09', '2025-01-09'),
    ('27–28 February', '2025-02-27', '2025-02-28'),
    ('31 March—2 April', '2025-03-31', '2025-04-02'),
    ('12 - 14 March [ 1 ]', '2025-03-12', '2025-03-14'),
    (' 9\u00a0January [2] ', '2025-01-09', '2025-01-09'),
])
def test_supported_dates(text, start, end):
    assert parse_visit_dates(text, 2025) == (date.fromisoformat(start), date.fromisoformat(end))


@pytest.mark.parametrize('text', ['', '29 February', '31 April', '14–12 March',
                                  '9 Unknown', 'TBD', '31 December–2 January'])
def test_invalid_or_unsupported_dates_are_rejected(text):
    with pytest.raises(ValueError):
        parse_visit_dates(text, 2025)


def test_normalize_preserves_country_and_source_fields():
    raw = {'date_raw': '9 January', 'year': 2025,
           'host_country_raw': ' Trinidad  and Tobago [1] ', 'details_raw': 'France and Argentina'}
    normalized = normalize_visit(raw)
    assert normalized['host_country_name'] == 'Trinidad and Tobago'
    assert all(normalized[key] == value for key, value in raw.items())
    assert 'start_date' not in raw


@pytest.mark.parametrize(('details', 'host', 'expected'), [
    ('Transited through Italy on the way to the summit.', 'Italy', True),
    ('The delegation made a refueling stop at RAF Mildenhall in the United Kingdom.', 'United Arab Emirates', False),
    ('The delegation made a refueling stop at RAF Mildenhall in the United Kingdom.', 'United Kingdom', True),
    ('The delegation attended a meeting in Rome.', 'Italy', False),
    ('', 'Italy', None),
    (None, 'Italy', None),
])
def test_transit_flag_uses_host_country_guard(details, host, expected):
    normalized = normalize_visit({
        'date_raw': '9 January', 'year': 2025,
        'host_country_raw': host, 'details_raw': details,
    })
    assert normalized['is_transit'] is expected
