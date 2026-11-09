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

    finish = EmptyOperator(task_id="finish")
    staging = build_gdelt_staging()
    quality_gate = run_gdelt_quality_gate()
    production = load_gdelt_fact()
    start >> staging >> quality_gate >> production >> finish
