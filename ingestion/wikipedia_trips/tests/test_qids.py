import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from ingestion.wikipedia_trips.qid_resolver import resolve_host_country_qids, resolve_page_qids
from ingestion.wikipedia_trips.scraper import fetch_page_qids, parse_page_qids


def test_normalizations_redirects_and_all_statuses():
    query = {
        'normalized': [{'from': 'united_kingdom', 'to': 'United kingdom'}],
        'redirects': [{'from': 'United kingdom', 'to': 'United Kingdom'}],
        'pages': [
            {'title': 'United Kingdom', 'ns': 0, 'pageprops': {'wikibase_item': 'Q145'}},
            {'title': 'Congo', 'ns': 0, 'pageprops': {'disambiguation': '', 'wikibase_item': 'Q1'}},
            {'title': 'Absent', 'missing': True},
            {'title': 'No item', 'ns': 0},
            {'title': 'Invalid', 'invalid': True},
            {'title': 'Talk:Country', 'ns': 1, 'pageprops': {'wikibase_item': 'Q2'}},
        ],
    }
    names = ['united_kingdom', 'Congo', 'Absent', 'No item', 'Invalid', 'Talk:Country']
    results = parse_page_qids(query, names)
    assert results['united_kingdom']['qid'] == 'Q145'
    assert results['united_kingdom']['resolved_title'] == 'United Kingdom'
    assert [results[name]['status'] for name in names] == [
        'resolved', 'disambiguation', 'missing', 'no_qid', 'invalid_title', 'not_article']
    assert all(results[name]['qid'] is None for name in names[1:])


def test_batching_deduplicates_titles_and_throttles():
    session = MagicMock()
    def response_for_titles(*args, **kwargs):
        response = MagicMock()
        response.json.return_value = {'query': {'pages': [
            {'title': title, 'ns': 0, 'pageprops': {'wikibase_item': 'Q1'}}
            for title in kwargs['params']['titles'].split('|')
        ]}}
        return response
    session.get.side_effect = response_for_titles
    with patch('ingestion.wikipedia_trips.scraper.requests.Session') as factory, \
         patch('ingestion.wikipedia_trips.scraper.time.sleep') as sleep:
        factory.return_value.__enter__.return_value = session
        results = fetch_page_qids([f'Country {index}' for index in range(51)] + ['Country 0'])
    assert len(results) == 51
    assert session.get.call_count == 2
    assert len(session.get.call_args_list[0].kwargs['params']['titles'].split('|')) == 50
    sleep.assert_called_once_with(1.0)


def test_cache_reuse_refresh_and_language_separation(tmp_path):
    cache = tmp_path / 'qids.json'
    answer = {'France': {'qid': 'Q142', 'status': 'resolved', 'resolved_title': 'France'}}
    with patch('ingestion.wikipedia_trips.qid_resolver.fetch_page_qids', return_value=answer) as fetch:
        resolve_page_qids(['France', 'France'], cache_path=cache)
        resolve_page_qids(['France'], cache_path=cache)
        assert fetch.call_count == 1
        resolve_page_qids(['France'], cache_path=cache, refresh=True)
        assert fetch.call_count == 2
        resolve_page_qids(['France'], language='fr', cache_path=cache)
        assert fetch.call_count == 3
    contents = json.loads(cache.read_text())
    assert set(contents) == {'en', 'fr'}
    assert contents['en']['France']['resolved_at']


@pytest.mark.parametrize('error', [requests.Timeout('timeout'), RuntimeError('maxlag')])
def test_network_or_api_failure_does_not_poison_cache(tmp_path, error):
    cache = tmp_path / 'qids.json'
    original = {'en': {'France': {'qid': 'Q142', 'resolved_title': 'France', 'status': 'resolved'}}}
    cache.write_text(json.dumps(original))
    before = cache.read_bytes()
    with patch('ingestion.wikipedia_trips.qid_resolver.fetch_page_qids', side_effect=error):
        with pytest.raises(type(error)):
            resolve_page_qids(['New country'], cache_path=cache)
    assert cache.read_bytes() == before


def test_empty_and_unresolved_names_are_not_dropped(tmp_path):
    visits = [{'host_country_name': name, 'wiki_language': 'en'} for name in ['', 'Congo', 'Missing']]
    answer = {
        'Congo': {'qid': None, 'resolved_title': 'Congo', 'status': 'disambiguation'},
        'Missing': {'qid': None, 'resolved_title': 'Missing', 'status': 'missing'},
    }
    with patch('ingestion.wikipedia_trips.qid_resolver.fetch_page_qids', return_value=answer) as fetch:
        enriched = resolve_host_country_qids(visits, tmp_path / 'cache.json')
        resolve_host_country_qids(visits, tmp_path / 'cache.json')
        fetch.assert_called_once_with(['Congo', 'Missing'], 'en')
    assert len(enriched) == len(visits)
    assert [visit['host_country_qid_status'] for visit in enriched] == ['empty_name', 'disambiguation', 'missing']
    assert all('host_country_qid' not in visit for visit in visits)
