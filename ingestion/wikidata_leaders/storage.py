import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "data/raw_landing/wikidata"
DEFAULT_NORMALIZED_OUTPUT = Path(__file__).resolve().parents[2] / "data/normalized/wikidata"
DEFAULT_RESOLVED_OUTPUT = Path(__file__).resolve().parents[2] / "data/resolved/wikidata"


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

def load_saved_query_response(directory):
    """Read one captured batch locally without calling the SPARQL endpoint"""
    directory = Path(directory)
    response = json.loads((directory / "response.json").read_text(encoding="utf-8"))
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    return response, metadata


def save_normalized_collection(records, review_items, manifest, directory):
    """Write derived records separately from the immutable raw collection"""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    files = {
        "office_statements.json": records["leaders"],
        "countries.json": records["countries"],
        "normalization_issues.json": review_items,
        "manifest.json": manifest,
    }
    for filename, content in files.items():
        (directory / filename).write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def load_normalized_collection(directory):
    """Read the completed normalized inputs needed for entity resolution."""
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["status"] not in ("complete", "complete_with_issues"):
        raise ValueError("Use a completed normalized collection")
    return {
        name: json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("office_statements", "countries", "normalization_issues")
    }


def save_resolution_results(results, directory):
    """Keep resolution results and review issues separate from normalized inputs."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in results.items():
        (directory / f"{name}.json").write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
