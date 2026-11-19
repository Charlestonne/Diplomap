import argparse
import json
from pathlib import Path

import yaml

from warehouse.duckdb_client import DEFAULT_DATABASE, execute_sql_file, open_database


WAREHOUSE_DIRECTORY = Path(__file__).resolve().parent
SCHEMA_FILE = WAREHOUSE_DIRECTORY / "dimensions_and_facts/schema.sql"
DIMENSIONS_FILE = WAREHOUSE_DIRECTORY / "dimensions_and_facts/dimensions.sql"
FACTS_FILE = WAREHOUSE_DIRECTORY / "dimensions_and_facts/facts.sql"
DEFAULT_ANALYSIS_CONFIG = WAREHOUSE_DIRECTORY.parent / "ingestion/config/analysis.yaml"


def load_production(database_path=DEFAULT_DATABASE, analysis_config=DEFAULT_ANALYSIS_CONFIG):
    """Rebuild production tables from the current DuckDB staging snapshot"""
    analysis = read_analysis_config(analysis_config)
    with open_database(database_path) as connection:
        connection.execute("BEGIN TRANSACTION")
        try:
            set_analysis_variables(connection, analysis)
            execute_sql_file(connection, SCHEMA_FILE)
            execute_sql_file(connection, DIMENSIONS_FILE)
            execute_sql_file(connection, FACTS_FILE)
            validate_windows(connection, analysis["window_days"])
            summary = production_summary(connection)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
    return {"database_path": str(database_path), "tables": summary}


def read_analysis_config(config_path):
    values = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("Analysis configuration must be a mapping")
    required = {"start_date", "end_date", "window_days"}
    if not required.issubset(values):
        raise ValueError(f"Analysis configuration must contain {sorted(required)}")
    window_days = int(values["window_days"])
    if window_days < 0:
        raise ValueError("window_days must be non-negative")
    return {
        "start_date": str(values["start_date"]),
        "end_date": str(values["end_date"]),
        "window_days": window_days,
    }


def set_analysis_variables(connection, analysis):
    connection.execute("SET VARIABLE analysis_start_date = ?", [analysis["start_date"]])
    connection.execute("SET VARIABLE analysis_end_date = ?", [analysis["end_date"]])
    connection.execute("SET VARIABLE analysis_window_days = ?", [analysis["window_days"]])


def validate_windows(connection, window_days):
    invalid_count = connection.execute(
        """
        SELECT count(*)
        FROM fact_visit
        WHERE pre_window_start <> start_date_key - ?
           OR pre_window_end <> start_date_key - 1
           OR post_window_start <> end_date_key + 1
           OR post_window_end <> end_date_key + ?
        """,
        [window_days, window_days],
    ).fetchone()[0]
    if invalid_count:
        raise ValueError(f"{invalid_count} fact_visit rows have invalid analysis windows")


def production_summary(connection):
    table_names = (
        "dim_country", "dim_date", "dim_event_type", "dim_visit_type",
        "dim_leader", "fact_visit", "fact_gdelt_event",
    )
    return {
        table_name: connection.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
        for table_name in table_names
    }


def main():
    parser = argparse.ArgumentParser(description="Build DuckDB production dimensions and facts")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--analysis-config", default=DEFAULT_ANALYSIS_CONFIG)
    arguments = parser.parse_args()
    print(json.dumps(load_production(arguments.database, arguments.analysis_config), indent=2))


if __name__ == "__main__":
    main()
