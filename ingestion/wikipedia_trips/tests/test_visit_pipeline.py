import json
from unittest.mock import patch

import pytest

from ingestion.wikipedia_trips.__main__ import main
from ingestion.wikipedia_trips.ingestion_pipeline import extract_page_visits
from ingestion.wikipedia_trips.storage import save_raw_page


HTML = '''
<h2>2024</h2><table class="wikitable"><tr><td>Ignore</td></tr></table>
<h2>2025</h2><h3>Trips</h3>
<table class="wikitable">
<tr><th>Country</th><th>Areas visited</th><th>Date(s)</th><th>Details</th></tr>
<tr><td rowspan="2">Qatar [1]</td><td>Lusail</td><td>1 January</td><td>France and Argentina</td></tr>
<tr><td>Doha</td><td>30 June–2 July</td><td>Meeting</td></tr>
<tr><td>France</td><td>Paris</td><td>1 July</td><td>Outside scope</td></tr>
<tr><td>France</td><td>Paris</td><td>TBD</td><td>Unknown date</td></tr>
</table>
<h2>2026</h2><table class="wikitable"><tr><td>Ignore</td></tr></table>
'''


def test_parser_handles_subsections_and_country_rowspans():
    visits = extract_page_visits({'text': HTML, 'pageid': 10, 'revid': 20}, 'Leader', 2025)
    assert len(visits) == 4
    assert [visit['host_country_raw'] for visit in visits[:2]] == ['Qatar [1]', 'Qatar [1]']
    assert visits[0]['details_raw'] == 'France and Argentina'
    assert visits[1]['source_row_index'] == 2


def test_cli_saved_html_through_qid_cache_and_output_files(tmp_path, monkeypatch, capsys):
    capture = save_raw_page(
        'macron',
        {'title': 'List of international presidential trips made by Emmanuel Macron',
         'language': 'en', 'years': [2025]},
                            {'text': HTML, 'pageid': 10, 'revid': 20}, tmp_path / 'raw')
    # Keep this integration test independent from the production inventory.
    # The saved capture identifies its leader as ``macron``, so the fixture
    # inventory must contain the same local identifier and page title.
    inventory = tmp_path / 'leaders.yaml'
    inventory.write_text(
        """
- leader_id: macron
  leader_name: Emmanuel Macron
  leader_page: Emmanuel Macron
  leader_language: en
  represented_country_iso3: FRA
  represented_country_qid: Q142
  position_qids: [Q191954]
  trips_pages:
    - title: Trips
      language: en
      years: [2025]
""",
        encoding='utf-8',
    )
    cache_path = tmp_path / 'cache.json'
    cache_path.write_text(json.dumps({'en': {
        'Qatar': {'qid': 'Q846', 'resolved_title': 'Qatar', 'status': 'resolved'},
        'Emmanuel Macron': {'qid': 'Q3052772', 'resolved_title': 'Emmanuel Macron', 'status': 'resolved'},
    }}))
    config = tmp_path / 'analysis.yaml'
    config.write_text('start_date: "2025-01-01"\nend_date: "2025-06-30"\n')
    output = tmp_path / 'output'
    monkeypatch.setattr('sys.argv', ['wikipedia_trips', '--normalize', '--saved-page', str(capture),
                                    '--leader', 'Emmanuel Macron', '--inventory', str(inventory),
                                    '--resolve-qids', '--qid-cache', str(cache_path),
                                    '--analysis-config', str(config), '--normalized-output', str(output)])
    with patch('ingestion.wikipedia_trips.qid_resolver.fetch_page_qids', side_effect=AssertionError('Unexpected network request')):
        main()
    files = list(output.rglob('visits.json'))
    assert len(files) == 1
    visits = json.loads(files[0].read_text())
    anomalies = json.loads(files[0].with_name('anomalies.json').read_text())
    assert len(visits) == 2
    assert visits[1]['end_date'] == '2025-07-02'  # Selection uses the start, not the end.
    assert all(visit['host_country_qid'] == 'Q846' for visit in visits)
    assert visits[0]['host_country_raw'] == 'Qatar [1]'
    assert visits[0]['host_country_name'] == 'Qatar'
    assert len(anomalies) == 1 and anomalies[0]['date_raw'] == 'TBD'
    assert anomalies[0]['error_code'] == 'invalid_visit_date'
    assert 'outside scope: 1' in capsys.readouterr().out


@pytest.mark.parametrize('arguments', [
    ['--resolve-qids'], ['--refresh-qids'], ['--normalize'],
    ['--collect', '--normalize', '--saved-page', 'unused'],
])
def test_cli_rejects_incompatible_options(arguments, monkeypatch):
    monkeypatch.setattr('sys.argv', ['wikipedia_trips', *arguments])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
