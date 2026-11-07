import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "data/raw/wikipedia"
DEFAULT_DATE_NORMALIZED_OUTPUT = Path(__file__).resolve().parents[2] / "data/date_normalized/wikipedia"


def save_raw_page(leader_id, source, page, output=DEFAULT_OUTPUT):
    """Save HTML and metadata once per Wikipedia revision"""
    html = page.get("text")
    # Validate inputs
    if not isinstance(html, str) or not html.strip():
        raise ValueError("Empty or invalid HTML")
    for field in ("pageid", "revid"):
        if type(page.get(field)) is not int or page[field] <= 0:
            raise ValueError(f"Missing or invalid {field}")

    language = source["language"]
    page_id = page["pageid"]
    revision_id = page["revid"]
    destination = (Path(output) / leader_id / language / str(page_id) / str(revision_id))
    html_path = destination / "page.html"
    metadata_path = destination / "metadata.json"
    if html_path.is_file() and metadata_path.is_file():
        return destination

    metadata = {
        "leader_id": leader_id,
        "page_title": page.get("title", source["title"]),
        "language": language,
        "page_id": page_id,
        "revision_id": revision_id,
        "source_url": f"https://{language}.wikipedia.org/w/index.php?oldid={revision_id}",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    destination.mkdir(parents=True, exist_ok=True)

    # Save the HTML + metadata to disk
    html_path.write_text(html, encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",encoding="utf-8",)
    return destination


def load_raw_page(directory):
    """Read a saved capture and its metadata"""
    directory = Path(directory)
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    return {
        "text": (directory / "page.html").read_text(encoding="utf-8"),
        "leader_local_id": metadata.get("leader_id"),
        "pageid": metadata["page_id"],
        "revid": metadata["revision_id"],
        "language": metadata["language"],
    }


def save_date_normalized_visits(visits, anomalies, directory):
    """Write both result lists including empty ones as JSON"""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for filename, records in (("visits.json", visits), ("anomalies.json", anomalies)):
        (directory / filename).write_text(
            json.dumps(records, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return directory


def save_multilateral_report(report, directory):
    """Keep source meetings and review items separate from date anomalies for multilateral visits"""
    destination = Path(directory) / "multilateral_meetings.json"
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
