import re
from pathlib import Path

import duckdb


DEFAULT_DATABASE = Path(__file__).resolve().parents[1] / "data/diplomap.duckdb"


def open_database(database_path=DEFAULT_DATABASE):
    if str(database_path) != ":memory:": # alternative for a temporary database
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(database_path))


def set_session_variables(connection, variables):
    """Set named SQL variables binding their values as parameters"""
    for name in variables:
        if not isinstance(name, str) or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
            raise ValueError(f"Invalid DuckDB variable name: {name!r}")
    for name, value in variables.items():
        if isinstance(value, Path):
            value = str(value)
        connection.execute(f"SET VARIABLE {name} = ?", [value])


def execute_sql_file(connection, sql_path, variables=None):
    """Run a SQL file and return the connection holding its last result"""
    sql = Path(sql_path).read_text(encoding="utf-8")
    if variables is not None:
        set_session_variables(connection, variables)
    return connection.execute(sql)
