import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "data/raw/wikipedia"


def save_raw_page(leader_id, source, page, output=DEFAULT_OUTPUT):
    """Save HTML and metadata once per Wikipedia revision."""
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
