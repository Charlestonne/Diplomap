"""Load a resolved collection's countries + rejections into DuckDB."""
import argparse
import json
from pathlib import Path

from warehouse.duckdb_client import DEFAULT_DATABASE, execute_sql_file, open_database


WAREHOUSE_DIRECTORY = Path(__file__).resolve().parents[1]


def validate_country_collection(collection_path):
    """Reject incomplete/malformed inputs before changing the db"""
    directory = Path(collection_path).resolve()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("stage") != "entity_resolution_not_warehouse_loading":
        raise ValueError("Use a resolved Wikidata collection, not raw or normalized data")
    if manifest.get("status") not in ("checked", "needs_review"):
        raise ValueError("Use a completed resolved collection")
    countries_file = directory / "countries.json"
    countries = json.loads(countries_file.read_text(encoding="utf-8"))
    if not isinstance(countries, list) or any(not isinstance(country, dict) for country in countries):
        raise ValueError("countries.json must contain an array of country objects")
    if manifest.get("country_count") != len(countries):
        raise ValueError("Country count does not match the resolved collection manifest")
    if not directory.name.strip():
        raise ValueError("A collection directory name is required")
    return directory, countries_file


def summarize_country_load(connection, collection_id):
    """Check that each source row was accepted or rejected + count reasons separately"""
    read_count = connection.execute("SELECT count(*) FROM country_candidates").fetchone()[0]
    accepted_count = connection.execute(
        "SELECT count(*) FROM stg_country WHERE collection_id = ?", [collection_id]
    ).fetchone()[0]
    rejected_count, reason_count = connection.execute(
        """SELECT count(DISTINCT source_row_index), count(*)
           FROM stg_quarantine
           WHERE collection_id = ? AND target_table = 'stg_country'""",
        [collection_id],
    ).fetchone()
    if read_count != accepted_count + rejected_count:
        raise ValueError("Country load lost or multiplied source records")
    return {
        "collection_id": collection_id,
        "status": "loaded_with_rejections" if rejected_count else "loaded",
        "read_count": read_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "rejection_reason_count": reason_count,
    }


def load_country_collection(collection_path, database_path=DEFAULT_DATABASE):
    """Replace one collection's country results atomically; safe to call from Airflow"""
    directory, countries_file = validate_country_collection(collection_path)
    with open_database(database_path) as connection:
        connection.execute("BEGIN TRANSACTION")
        try:
            execute_sql_file(connection, WAREHOUSE_DIRECTORY / "staging/schema.sql")
            execute_sql_file(connection, WAREHOUSE_DIRECTORY / "quality_gate/schema.sql")
            execute_sql_file(
                connection, WAREHOUSE_DIRECTORY / "staging/countries.sql",
                variables={"collection_id": directory.name, "countries_file": countries_file},
            )
            summary = summarize_country_load(connection, directory.name)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
    return {**summary, "database_path": str(database_path), "source_file": str(countries_file)}


def main():
    parser = argparse.ArgumentParser(description="Load countries and quarantine into DuckDB staging")
    parser.add_argument("--collection", required=True, help="Resolved Wikidata collection directory")
    parser.add_argument("--database", default=DEFAULT_DATABASE, help="Persistent DuckDB database path")
    args = parser.parse_args()
    summary = load_country_collection(args.collection, args.database)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
