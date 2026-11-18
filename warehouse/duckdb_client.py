from pathlib import Path

import duckdb


DEFAULT_DATABASE = Path(__file__).resolve().parents[1] / "data/diplomap.duckdb"


def open_database(database_path=DEFAULT_DATABASE):
    if str(database_path) != ":memory:": # alternative for a temporary database
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(database_path))


def execute_sql_file(connection, sql_path):
    """Run a schema SQL file and return the connection holding its last result."""
    sql = Path(sql_path).read_text(encoding="utf-8")
    return connection.execute(sql)
