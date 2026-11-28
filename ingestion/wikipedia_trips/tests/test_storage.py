import json
from unittest.mock import patch

import pytest

from ingestion.wikipedia_trips.storage import save_raw_page
from ingestion.wikipedia_trips.ingestion_pipeline import collect_pages
from ingestion.wikipedia_trips.inventory import load_inventory


SOURCE = {"title": "Trips", "language": "en", "years": [2025]}
PAGE = {"text": "<h2>2025</h2>", "pageid": 10, "revid": 20}


def test_save_preserves_html_and_first_capture(tmp_path):
    path = save_raw_page("macron", SOURCE, PAGE, tmp_path)
    assert (path / "page.html").read_text() == PAGE["text"]
    metadata = json.loads((path / "metadata.json").read_text())
    assert metadata["revision_id"] == 20
    assert metadata["source_url"].endswith("oldid=20")
    before = (path / "metadata.json").read_bytes()
    save_raw_page("macron", SOURCE, {**PAGE, "text": "changed template"}, tmp_path)
    assert (path / "metadata.json").read_bytes() == before
    assert (path / "page.html").read_text() == PAGE["text"]
    newer = save_raw_page("macron", SOURCE, {**PAGE, "revid": 21}, tmp_path)
    assert newer != path


@pytest.mark.parametrize("changes", [{"text": ""}, {"pageid": None}, {"revid": -1}])
def test_invalid_response_is_not_saved(tmp_path, changes):
    with pytest.raises(ValueError):
        save_raw_page("macron", SOURCE, {**PAGE, **changes}, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_collect_inventory_and_report_failure(tmp_path):
    assert load_inventory()[0]["leader_id"] == "macron"
    with patch("ingestion.wikipedia_trips.ingestion_pipeline.fetch_wikipedia_page", return_value=PAGE):
        assert len(collect_pages(output=tmp_path)) == 1
    with patch("ingestion.wikipedia_trips.ingestion_pipeline.fetch_wikipedia_page", side_effect=TimeoutError):
        with pytest.raises(TimeoutError):
            collect_pages(output=tmp_path, refresh=True)


def test_collect_reuses_complete_capture_without_downloading(tmp_path):
    with patch("ingestion.wikipedia_trips.ingestion_pipeline.fetch_wikipedia_page", return_value=PAGE) as fetch:
        first = collect_pages(output=tmp_path)
        second = collect_pages(output=tmp_path)

    assert second == first
    fetch.assert_called_once()


def test_incomplete_save_can_be_retried(tmp_path):
    path = save_raw_page("macron", SOURCE, PAGE, tmp_path)
    (path / "metadata.json").unlink()
    save_raw_page("macron", SOURCE, PAGE, tmp_path)
    assert json.loads((path / "metadata.json").read_text())["revision_id"] == 20
