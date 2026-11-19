import argparse
import json
from pathlib import Path

from warehouse.duckdb_client import DEFAULT_DATABASE, execute_sql_file, open_database


WAREHOUSE_DIRECTORY = Path(__file__).resolve().parent
SCHEMA_FILE = WAREHOUSE_DIRECTORY / "dimensions_and_facts/schema.sql"
DIMENSIONS_FILE = WAREHOUSE_DIRECTORY / "dimensions_and_facts/dimensions.sql"
FACTS_FILE = WAREHOUSE_DIRECTORY / "dimensions_and_facts/facts.sql"


def load_production(database_path=DEFAULT_DATABASE):
    """Rebuild production tables from the current DuckDB staging snapshot"""
    with open_database(database_path) as connection:
        connection.execute("BEGIN TRANSACTION")
        try:
            execute_sql_file(connection, SCHEMA_FILE)
            execute_sql_file(connection, DIMENSIONS_FILE)
            execute_sql_file(connection, FACTS_FILE)
            summary = production_summary(connection)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
    return {"database_path": str(database_path), "tables": summary}


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
    arguments = parser.parse_args()
    print(json.dumps(load_production(arguments.database), indent=2))


if __name__ == "__main__":
    main()
