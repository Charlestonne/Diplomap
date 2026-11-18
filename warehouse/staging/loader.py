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

def blank(values):
    return values.isna() | values.astype(str).str.strip().eq("")


def matches(values, pattern):
    return values.fillna("").astype(str).map(lambda value: bool(pattern.fullmatch(value)))


def duplicated_values(frame, column):
    return ~blank(frame[column]) & frame.duplicated(column, keep=False)


def conflicting_codes(frame, column):
    non_empty = frame.loc[~blank(frame[column]), [column, "country_qid"]]
    conflicts = non_empty.groupby(column)["country_qid"].nunique()
    return frame[column].isin(conflicts[conflicts.gt(1)].index)

def add_reason(frame, condition, reason):
    """Append one review reason to each row selected by a boolean condition"""
    for index in frame.index[condition.fillna(True)]:
        frame.at[index, "rejection_reasons"].append(reason)


def split_candidates(frame):
    rejected = frame[frame["rejection_reasons"].map(bool)].copy()
    accepted = frame[~frame["rejection_reasons"].map(bool)].copy()
    return CandidateRows(accepted=accepted, rejected=rejected)

def validate_countries(candidates):
    """Apply the stg_country rules without dropping the rows that fail them"""
    frame = candidates.copy()
    add_reason(frame, frame["reference_status"].ne("checked"), "country_not_checked")
    add_reason(frame, ~matches(frame["country_qid"], QID_PATTERN), "invalid_country_qid")
    add_reason(frame, blank(frame["country_name"]), "missing_country_name")
    add_reason(frame, ~matches(frame["iso3_code"], ISO3_PATTERN), "missing_or_invalid_iso3")
    add_reason(
        frame,
        frame["fips_code"].notna() & ~matches(frame["fips_code"], FIPS_PATTERN),
        "invalid_fips",
    )
    add_reason(frame, duplicated_values(frame, "country_qid"), "duplicate_country_qid")
    add_reason(frame, conflicting_codes(frame, "iso3_code"), "conflicting_iso3_code")
    add_reason(frame, conflicting_codes(frame, "fips_code"), "conflicting_fips_code")
    return split_candidates(frame)

