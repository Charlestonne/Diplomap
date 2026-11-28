"""Load one resolved Wikidata collection into the DuckDB staging tables"""

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from warehouse.duckdb_client import DEFAULT_DATABASE, execute_sql_file, open_database
from warehouse.staging.country_reference import (
    DEFAULT_CAMEO_FILE,
    DEFAULT_ISO_FILE,
    load_country_reference,
)
from ingestion.wikipedia_trips.transit import is_transit


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


def load_staging_collection(
    collection_path,
    database_path=DEFAULT_DATABASE,
    cameo_file=DEFAULT_CAMEO_FILE,
    iso_file=DEFAULT_ISO_FILE,
):
    """Replace a collection's staging rows atomically and return load counts"""
    collection_path = validate_collection(collection_path)
    collection_id = collection_path.name

    countries = validate_countries(read_records(collection_path, "countries"))
    leaders = validate_leaders(read_records(collection_path, "office_periods"), countries.accepted)
    visits = validate_visits(read_records(collection_path, "visits"), countries.accepted, leaders.accepted)

    with open_database(database_path) as connection:
        connection.execute("BEGIN TRANSACTION")
        try:
            create_staging_tables(connection)
            reference_summary = load_country_reference(connection, cameo_file, iso_file)
            replace_collection_rows(connection, collection_id, countries, leaders, visits)
            summary = build_summary(collection_id, countries, leaders, visits)
            summary["country_reference"] = reference_summary
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise

    return {**summary, "database_path": str(database_path), "collection_path": str(collection_path)}


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



def date_columns(frame, start_column, end_column):
    return pd.DataFrame({
        start_column: pd.to_datetime(frame[start_column], errors="coerce"),
        end_column: pd.to_datetime(frame[end_column], errors="coerce"),
    })


def add_date_reasons(frame, start_column, end_column):
    dates = date_columns(frame, start_column, end_column)
    add_reason(frame, dates[start_column].isna(), f"invalid_{start_column}")
    add_reason(frame, frame[end_column].notna() & dates[end_column].isna(), f"invalid_{end_column}")
    add_reason(
        frame,
        dates[start_column].notna() & dates[end_column].notna() & dates[end_column].lt(dates[start_column]),
        "end_before_start",
    )


def invalid_end_date_status(frame):
    return (
        (frame["valid_to"].isna() & frame["end_date_status"].ne("not_reported_open_interval"))
        | (frame["valid_to"].notna() & frame["end_date_status"].ne("reported"))
    )


def add_overlapping_office_reason(frame):
    dates = date_columns(frame, "valid_from", "valid_to")
    for leader_qid, leader_rows in frame.groupby("leader_qid"):
        del leader_qid
        ordered = leader_rows.assign(_from=dates.loc[leader_rows.index, "valid_from"], _to=dates.loc[leader_rows.index, "valid_to"])
        ordered = ordered.sort_values("_from")
        latest_end = None
        for index, row in ordered.iterrows():
            end = row["_to"]
            if latest_end is not None and row["_from"] <= latest_end:
                add_reason(frame, pd.Series(frame.index == index, index=frame.index), "overlapping_office_period")
            if pd.isna(end):
                latest_end = pd.Timestamp.max
            elif latest_end is None or end > latest_end:
                latest_end = end


def validate_leaders(candidates, accepted_countries):
    """Validate source office periods and their country reference"""
    frame = candidates.copy()
    # Resolution already exposes valid_from/valid_to.  Keep the fallback for a
    # collection produced by the older normalizer, which only exposed dates.
    if "valid_from" not in frame:
        frame = frame.rename(columns={"start_date": "valid_from"})
    if "valid_to" not in frame:
        frame = frame.rename(columns={"end_date": "valid_to"})
    add_reason(frame, blank(frame["leader_local_id"]), "missing_leader_local_id")
    add_reason(frame, blank(frame["leader_name"]), "missing_leader_name")
    add_reason(frame, ~matches(frame["leader_qid"], QID_PATTERN), "invalid_leader_qid")
    add_reason(frame, ~matches(frame["position_qid"], QID_PATTERN), "invalid_position_qid")
    add_reason(frame, ~matches(frame["statement_uri"], STATEMENT_PATTERN), "invalid_statement_uri")
    add_reason(frame, ~matches(frame["represented_country_iso3"], ISO3_PATTERN), "invalid_represented_country_iso3")
    add_reason(
        frame,
        ~frame["represented_country_iso3"].isin(accepted_countries["iso3_code"]),
        "unknown_represented_country",
    )
    add_date_reasons(frame, "valid_from", "valid_to")
    add_reason(frame, invalid_end_date_status(frame), "invalid_end_date_status")
    add_reason(frame, duplicated_values(frame, "statement_uri"), "duplicate_statement_uri")
    add_overlapping_office_reason(frame)
    return split_candidates(frame)

def positive_integers(values):
    numeric_values = pd.to_numeric(values, errors="coerce")
    return numeric_values.notna() & numeric_values.gt(0) & numeric_values.mod(1).eq(0)


def matches_country(frame, role, countries):
    expected = countries.set_index("country_qid")["iso3_code"]
    return frame[f"{role}_country_qid"].map(expected).eq(frame[f"{role}_country_iso3"])


def matches_leader(visits, leaders):
    leader_lookup = leaders.set_index("statement_uri")
    return (
        visits["office_statement_uri"].map(leader_lookup["leader_qid"]).eq(visits["leader_qid"])
        & visits["office_statement_uri"].map(leader_lookup["represented_country_iso3"]).eq(visits["visitor_country_iso3"])
    )


def office_valid_on_visit_start(visits, leaders):
    leader_lookup = leaders.set_index("statement_uri")
    visit_date = pd.to_datetime(visits["start_date"], errors="coerce")
    valid_from = pd.to_datetime(visits["office_statement_uri"].map(leader_lookup["valid_from"]), errors="coerce")
    valid_to = pd.to_datetime(visits["office_statement_uri"].map(leader_lookup["valid_to"]), errors="coerce")
    return visit_date.ge(valid_from) & (valid_to.isna() | visit_date.le(valid_to))


def validate_visits(candidates, accepted_countries, accepted_leaders):
    """Validate fully resolved visits and the references needed by staging"""
    frame = candidates.copy()
    # Older resolved collections may predate this derived field. Recompute it
    # from preserved raw text so they remain loadable after the schema change.
    if "is_transit" not in frame:
        frame["is_transit"] = frame.apply(
            lambda row: is_transit(row.get("details_raw"), row.get("host_country_raw")), axis=1
        )
    add_reason(frame, frame["resolution_status"].ne("resolved"), "visit_not_resolved")
    add_reason(frame, frame["office_resolution_status"].ne("resolved"), "office_not_resolved")
    add_reason(frame, frame["country_resolution_status"].ne("resolved"), "country_not_resolved")
    add_reason(frame, frame["resolution_blockers"].map(bool), "resolution_blockers_present")
    for column, reason in (
        ("leader_qid", "invalid_leader_qid"),
        ("visitor_country_qid", "invalid_visitor_country_qid"),
        ("host_country_qid", "invalid_host_country_qid"),
    ):
        add_reason(frame, ~matches(frame[column], QID_PATTERN), reason)
    add_reason(frame, ~matches(frame["visitor_country_iso3"], ISO3_PATTERN), "invalid_visitor_country_iso3")
    add_reason(frame, ~matches(frame["host_country_iso3"], ISO3_PATTERN), "invalid_host_country_iso3")
    add_reason(frame, ~matches(frame["office_statement_uri"], STATEMENT_PATTERN), "invalid_statement_uri")
    add_date_reasons(frame, "start_date", "end_date")
    dates = date_columns(frame, "start_date", "end_date")
    expected_duration = (dates["end_date"] - dates["start_date"]).dt.days + 1
    add_reason(frame, frame["duration_days"].ne(expected_duration) | frame["duration_days"].lt(1), "invalid_duration")
    add_reason(frame, frame["visitor_country_qid"].eq(frame["host_country_qid"]), "same_visitor_and_host")
    add_reason(frame, frame["wiki_language"].ne("en"), "unsupported_wiki_language")
    for column in ("wiki_page_id", "wiki_revision_id", "source_table_index", "source_row_index"):
        add_reason(frame, ~positive_integers(frame[column]), f"invalid_{column}")
    add_reason(frame, ~matches_country(frame, "visitor", accepted_countries), "unknown_visitor_country")
    add_reason(frame, ~matches_country(frame, "host", accepted_countries), "unknown_host_country")
    add_reason(frame, ~matches_leader(frame, accepted_leaders), "unknown_or_inconsistent_office")
    add_reason(frame, ~office_valid_on_visit_start(frame, accepted_leaders), "office_not_valid_on_visit_date")
    identity = ["wiki_language", "wiki_page_id", "wiki_revision_id", "source_table_index", "source_row_index"]
    add_reason(frame, frame.duplicated(identity, keep=False), "duplicate_source_coordinates")
    business_key = ["leader_qid", "host_country_qid", "start_date", "end_date", "areas_visited_raw"]
    add_reason(frame, frame.duplicated(business_key, keep=False), "possible_duplicate_visit")
    return split_candidates(frame)


def create_staging_tables(connection):
    execute_sql_file(connection, WAREHOUSE_DIRECTORY / "staging/schema.sql")
    execute_sql_file(connection, WAREHOUSE_DIRECTORY / "quality_gate/schema.sql")


def replace_collection_rows(connection, collection_id, countries, leaders, visits):
    """Delete and insert all rows for one collection in the current transaction"""
    for table in ("stg_country", "stg_leader", "stg_visit"):
        connection.execute(f"DELETE FROM {table} WHERE collection_id = ?", [collection_id])
    connection.execute("DELETE FROM stg_quarantine WHERE collection_id = ?", [collection_id])

    insert_rows(connection, "stg_country", countries.accepted, [
        "collection_id", "country_qid", "country_name", "iso3_code", "fips_code", "source_file", "source_record",
    ])
    insert_rows(connection, "stg_leader", leaders.accepted, [
        "collection_id", "statement_uri", "leader_local_id", "leader_qid", "leader_name", "position_qid",
        "position_title", "represented_country_iso3", "valid_from", "valid_to", "end_date_status", "source_file", "source_record",
    ])
    insert_rows(connection, "stg_visit", visits.accepted, [
        "collection_id", "leader_qid", "office_statement_uri", "visitor_country_qid", "visitor_country_iso3",
        "host_country_qid", "host_country_iso3", "start_date", "end_date", "duration_days", "is_multilateral", "is_transit",
        "wiki_language", "wiki_page_id", "wiki_revision_id", "source_table_index", "source_row_index",
        "host_country_raw", "date_raw", "areas_visited_raw", "details_raw", "source_file", "source_record",
    ])
    insert_quarantine_rows(connection, "stg_country", countries.rejected)
    insert_quarantine_rows(connection, "stg_leader", leaders.rejected)
    insert_quarantine_rows(connection, "stg_visit", visits.rejected)


def insert_rows(connection, table, frame, columns):
    if frame.empty:
        return
    relation_name = f"{table}_input"
    connection.register(relation_name, frame[columns])
    column_list = ", ".join(columns)
    connection.execute(f"INSERT INTO {table} ({column_list}) SELECT {column_list} FROM {relation_name}")
    connection.unregister(relation_name)


def insert_quarantine_rows(connection, target_table, rejected):
    rows = []
    for _, rejected_row in rejected.iterrows():
        for reason in rejected_row["rejection_reasons"]:
            rows.append({
                "collection_id": rejected_row["collection_id"],
                "target_table": target_table,
                "source_row_index": rejected_row["source_row_index"],
                "rejection_reason": reason,
                "source_file": rejected_row["source_file"],
                "source_record": rejected_row["source_record"],
            })
    insert_rows(connection, "stg_quarantine", pd.DataFrame(rows), [
        "collection_id", "target_table", "source_row_index", "rejection_reason", "source_file", "source_record",
    ])


def build_summary(collection_id, countries, leaders, visits):
    summary = {"collection_id": collection_id, "tables": {}}
    for table, rows in (("countries", countries), ("leaders", leaders), ("visits", visits)):
        summary["tables"][table] = {
            "accepted": len(rows.accepted),
            "rejected": len(rows.rejected),
            "rejection_reasons": sum(len(reasons) for reasons in rows.rejected["rejection_reasons"]),
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Load one resolved Wikidata collection into DuckDB staging")
    parser.add_argument("--collection", required=True, help="Resolved Wikidata collection directory")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="DuckDB database path")
    parser.add_argument("--cameo-file", default=DEFAULT_CAMEO_FILE, help="CAMEO country reference path")
    parser.add_argument("--iso-file", default=DEFAULT_ISO_FILE, help="ISO country reference path")
    arguments = parser.parse_args()
    print(json.dumps(
        load_staging_collection(
            arguments.collection,
            arguments.database,
            arguments.cameo_file,
            arguments.iso_file,
        ),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
