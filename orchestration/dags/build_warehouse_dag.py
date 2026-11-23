"""Build staging and production tables for the warehouse"""

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import DAG, task
from pendulum import datetime

from assets import gdelt_landing, wikidata_landing


with DAG(
    dag_id="diplomap_build_warehouse",
    start_date=datetime(2024, 12, 17, tz="UTC"),
    schedule=[gdelt_landing, wikidata_landing],
    catchup=False,
    tags=["diplomap", "warehouse"],
) as dag:
    start = EmptyOperator(task_id="start")

    @task(pool="duckdb_writer")
    def load_staging_collection_task() -> dict:
        from pathlib import Path

        from warehouse.staging.loader import load_staging_collection

        resolved_root = Path("/data/resolved/wikidata")
        if not resolved_root.is_dir():
            raise RuntimeError(f"Resolved Wikidata directory does not exist: {resolved_root}")
        collections = sorted(
            path
            for path in resolved_root.iterdir()
            if path.is_dir() and (path / "manifest.json").is_file()
        )

        if not collections:
            raise RuntimeError(f"No resolved Wikidata collection found in {resolved_root}")

        return load_staging_collection(
            collection_path=collections[-1],
            database_path="/data/warehouse/diplomap.duckdb",
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
        import duckdb
        from pathlib import Path

        from warehouse.quality_gate import quarantine

        database = Path("/data/warehouse/diplomap.duckdb")
        with duckdb.connect(str(database)) as connection:
            results = quarantine.run(connection, ["stg_gdelt_event"])
        missing = [result["rule_id"] for result in results if result["status"] == "table_missing"]
        if missing:
            raise RuntimeError(f"GDELT quality gate could not find required tables: {missing}")

    @task(pool="duckdb_writer")
    def load_production_warehouse() -> dict:
        from warehouse.production_loader import load_production

        return load_production(database_path="/data/warehouse/diplomap.duckdb")

    @task(pool="duckdb_writer")
    def validate_production_warehouse() -> dict:
        from pathlib import Path

        from warehouse.duckdb_client import open_database
        from warehouse.production_loader import production_summary

        database = Path("/data/warehouse/diplomap.duckdb")
        required_tables = {
            "dim_country",
            "dim_date",
            "dim_event_type",
            "dim_visit_type",
            "dim_leader",
            "fact_visit",
            "fact_gdelt_event",
        }
        with open_database(database) as connection:
            existing_tables = {
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main'"
                ).fetchall()
            }
            missing_tables = sorted(required_tables - existing_tables)
            if missing_tables:
                raise RuntimeError(f"Production tables are missing: {missing_tables}")

            summary = production_summary(connection)
            if any(count < 0 for count in summary.values()):
                raise RuntimeError(f"Invalid production row counts: {summary}")

        return summary

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

    staging_collection = load_staging_collection_task()
    gdelt_staging = build_gdelt_staging()
    gdelt_quality_gate = run_gdelt_quality_gate()
    production = load_production_warehouse()
    gdelt_fact = load_gdelt_fact()
    production_validation = validate_production_warehouse()

    # Existing GDELT path
    start >> staging_collection >> gdelt_staging
    gdelt_staging >> gdelt_quality_gate
    gdelt_quality_gate >> production >> gdelt_fact >> production_validation >> finish
