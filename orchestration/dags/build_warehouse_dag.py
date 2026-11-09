"""Build the GDELT staging tables and load the validated fact table."""

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import DAG, task
from pendulum import datetime

from assets import gdelt_landing


with DAG(
    dag_id="diplomap_build_warehouse",
    start_date=datetime(2024, 12, 17, tz="UTC"),
    schedule=gdelt_landing,
    catchup=False,
    tags=["diplomap", "warehouse"],
) as dag:
    start = EmptyOperator(task_id="start")

    @task(pool="duckdb_writer")
    def initialize_schema_and_dimensions() -> None:
        from pathlib import Path

        import duckdb

        database = Path("/data/warehouse/diplomap.duckdb")
        schema_sql = Path("/opt/diplomap/warehouse/dimensions_and_facts/schema.sql")
        dimensions_sql = Path("/opt/diplomap/warehouse/dimensions_and_facts/dimensions.sql")
        expected_tables = {
            "dim_country",
            "dim_date",
            "dim_event_type",
            "dim_visit_type",
            "dim_leader",
            "fact_visit",
            "fact_gdelt_event",
        }
        with duckdb.connect(str(database)) as connection:
            existing = {
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main'"
                ).fetchall()
            }
            if not expected_tables.issubset(existing):
                connection.execute(schema_sql.read_text(encoding="utf-8"))
            connection.execute(dimensions_sql.read_text(encoding="utf-8"))
            counts = {
                "dim_country": connection.execute("SELECT count(*) FROM dim_country").fetchone()[0],
                "dim_date": connection.execute("SELECT count(*) FROM dim_date").fetchone()[0],
                "dim_event_type": connection.execute("SELECT count(*) FROM dim_event_type").fetchone()[0],
            }
            expected_counts = {"dim_country": 233, "dim_date": 211, "dim_event_type": 310}
            if counts != expected_counts:
                raise RuntimeError(
                    f"Unexpected dimension counts: got {counts}, expected {expected_counts}"
                )

    @task(pool="duckdb_writer")
    def build_gdelt_staging() -> None:
        from pathlib import Path

        import duckdb

        database = Path("/data/warehouse/diplomap.duckdb")
        staging_sql = Path("/opt/diplomap/warehouse/staging/gdelt.sql")
        with duckdb.connect(str(database)) as connection:
            connection.execute(staging_sql.read_text(encoding="utf-8"))

    @task(pool="duckdb_writer")
    def run_gdelt_quality_gate() -> None:
        from pathlib import Path

        import duckdb

        from warehouse.quality_gate import quarantine

        database = Path("/data/warehouse/diplomap.duckdb")
        with duckdb.connect(str(database)) as connection:
            results = quarantine.run(connection, ["stg_gdelt_event"])
        missing = [result["rule_id"] for result in results if result["status"] == "table_missing"]
        if missing:
            raise RuntimeError(f"GDELT quality gate could not find required tables: {missing}")

    @task(pool="duckdb_writer")
    def load_gdelt_fact() -> None:
        from pathlib import Path

        import duckdb

        from warehouse.quality_gate import quarantine

        database = Path("/data/warehouse/diplomap.duckdb")
        candidate_sql = Path("/opt/diplomap/warehouse/dimensions_and_facts/fact_gdelt.sql")
        required_tables = {
            "dim_country",
            "dim_date",
            "dim_event_type",
            "fact_gdelt_event",
        }
        with duckdb.connect(str(database)) as connection:
            existing = {
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main'"
                ).fetchall()
            }
            missing = sorted(required_tables - existing)
            if missing:
                raise RuntimeError(
                    "The GDELT fact load requires prepared dimensions and schema; "
                    f"missing tables: {missing}"
                )
            connection.execute(candidate_sql.read_text(encoding="utf-8"))
            results = quarantine.run(connection, ["stg_fact_gdelt"])
            missing_candidate = [
                result["rule_id"]
                for result in results
                if result["status"] == "table_missing"
            ]
            if missing_candidate:
                raise RuntimeError("The fact candidate table was not created")
            connection.execute("DELETE FROM fact_gdelt_event")
            connection.execute(
                """
                INSERT INTO fact_gdelt_event
                SELECT gdelt_event_id, resolved_date_key, actor1_country_key,
                       actor2_country_key, event_type_key, source_url,
                       goldstein_scale, avg_tone, num_mentions
                FROM stg_fact_gdelt
                """
            )
            expected_rows = connection.execute("SELECT count(*) FROM stg_fact_gdelt").fetchone()[0]
            actual_rows = connection.execute("SELECT count(*) FROM fact_gdelt_event").fetchone()[0]
            duplicate_ids = connection.execute(
                """
                SELECT count(*)
                FROM (
                    SELECT gdelt_event_id
                    FROM fact_gdelt_event
                    GROUP BY gdelt_event_id
                    HAVING count(*) > 1
                )
                """
            ).fetchone()[0]
            if actual_rows != expected_rows or duplicate_ids:
                raise RuntimeError(
                    f"Fact row-count check failed: expected {expected_rows}, "
                    f"loaded {actual_rows}, duplicate ids {duplicate_ids}"
                )

    finish = EmptyOperator(task_id="finish")
    dimensions = initialize_schema_and_dimensions()
    staging = build_gdelt_staging()
    quality_gate = run_gdelt_quality_gate()
    production = load_gdelt_fact()
    start >> dimensions >> staging >> quality_gate >> production >> finish
