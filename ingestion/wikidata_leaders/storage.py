import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "data/raw_landing/wikidata"


def create_collection_directory(output=DEFAULT_OUTPUT):
    """Give each explicit collection run its own timestamped directory"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = Path(output) / timestamp
    directory.mkdir(parents=True)
    return directory


def save_query_response(response, query, metadata, directory):
    """Keep the complete JSON response, rendered query and request metadata"""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "query.sparql").write_text(query, encoding="utf-8")
    for filename, content in (("response.json", response), ("metadata.json", metadata)):
        (directory / filename).write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def save_collection_manifest(manifest, directory):
    """Record completed batches and any collection failure without losing prior results"""
    (Path(directory) / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
