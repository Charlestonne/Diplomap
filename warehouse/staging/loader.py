"""Load one resolved Wikidata collection into the DuckDB staging tables"""

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from warehouse.duckdb_client import DEFAULT_DATABASE, execute_sql_file, open_database


WAREHOUSE_DIRECTORY = Path(__file__).resolve().parents[1]
QID_PATTERN = re.compile(r"Q[1-9][0-9]*$")
ISO3_PATTERN = re.compile(r"[A-Z]{3}$")
FIPS_PATTERN = re.compile(r"[A-Z]{2}$")
STATEMENT_PATTERN = re.compile(r"https?://www[.]wikidata[.]org/entity/statement/.+$")


class CandidateRows:
    """Accepted rows and rejected rows from a single staging source"""

    def __init__(self, accepted, rejected):
        self.accepted = accepted
        self.rejected = rejected

def read_json_array(path):
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        raise ValueError(f"{path} must contain an array of JSON objects")
    return records


def read_records(collection_path, name):
    """Read one JSON array and retain its original object for quarantine"""
    source_file = collection_path / f"{name}.json"
    records = read_json_array(source_file)
    frame = pd.DataFrame(records)
    if frame.empty:
        frame = pd.DataFrame(index=range(0))
    frame["collection_id"] = collection_path.name
    frame["source_file"] = str(source_file)
    frame["source_row_index"] = range(1, len(frame) + 1)
    frame["source_record"] = [json.dumps(record, ensure_ascii=False) for record in records]
    frame["rejection_reasons"] = [[] for _ in range(len(frame))]
    return frame


def validate_collection(collection_path):
    """Check that the directory is a complete entity-resolution collection"""
    directory = Path(collection_path).resolve()
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("stage") != "entity_resolution_not_warehouse_loading":
        raise ValueError("Expected a resolved Wikidata collection")
    if manifest.get("status") not in {"checked", "needs_review"}:
        raise ValueError("The resolved collection is not complete")

    for filename, count_name in (
        ("countries.json", "country_count"),
        ("office_periods.json", "selected_office_periods"),
        ("visits.json", "visit_count"),
    ):
        records = read_json_array(directory / filename)
        if manifest.get(count_name) != len(records):
            raise ValueError(f"{filename} does not match {count_name} in the manifest")
    return directory

