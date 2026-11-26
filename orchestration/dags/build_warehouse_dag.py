"""Build the GDELT staging tables and load the validated fact table."""

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import DAG, Param, task
from pendulum import datetime

from assets import gdelt_landing


with DAG(
    dag_id="diplomap_build_warehouse",
    start_date=datetime(2024, 12, 17, tz="UTC"),
    schedule=gdelt_landing,
    catchup=False,
    tags=["diplomap", "warehouse"],
    params={
        "full_rebuild": Param(
            False,
            type="boolean",
            description="Drop ALL warehouse tables and rebuild them from schema.sql + dimensions.sql.",
        ),
        "confirm_data_loss": Param(
            False,
            type="boolean",
            description="Required if fact_visit or dim_leader contain rows (they are dropped, not rebuilt here).",
        ),
    },
) as dag:
    start = EmptyOperator(task_id="start")

    @task(pool="duckdb_writer")
    def initialize_schema_and_dimensions() -> None:
        import logging
        from pathlib import Path

        import duckdb
        from airflow.sdk import get_current_context
        from pendulum import now

        log = logging.getLogger(__name__)
        params = get_current_context()["params"]
        full_rebuild = bool(params.get("full_rebuild"))
        confirm_data_loss = bool(params.get("confirm_data_loss"))

        database = Path("/data/warehouse/diplomap.duckdb")
        schema_sql = Path("/opt/diplomap/warehouse/dimensions_and_facts/schema.sql")
        dimensions_sql = Path("/opt/diplomap/warehouse/dimensions_and_facts/dimensions.sql")
        expected_tables = {
            "dim_country", "dim_date", "dim_event_type", "dim_visit_type",
            "dim_leader", "fact_visit", "fact_gdelt_event",
        }
        # Children first, parents last (same order as schema.sql).
        drop_order = [
            "fact_gdelt_event", "fact_visit", "dim_leader", "dim_event_type",
            "dim_visit_type", "dim_date", "dim_country",
        ]
        not_rebuilt_here = ("fact_visit", "dim_leader", "dim_visit_type")

        with duckdb.connect(str(database)) as connection:
            existing = {
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main'"
                ).fetchall()
            }

            if full_rebuild:
                at_risk = {
                    table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    for table in not_rebuilt_here
                    if table in existing
                }
                at_risk = {table: n for table, n in at_risk.items() if n}
                if at_risk and not confirm_data_loss:
                    raise RuntimeError(
                        f"Full rebuild would destroy data not rebuilt by this DAG: {at_risk}. "
                        "Set confirm_data_loss=true to proceed."
                    )

                backup_dir = database.parent / "backups" / f"diplomap_{now('UTC').format('YYYYMMDD_HHmmss')}"
                backup_dir.mkdir(parents=True, exist_ok=True)
                connection.execute(f"EXPORT DATABASE '{backup_dir}' (FORMAT PARQUET)")
                log.warning("Full rebuild: backup written to %s", backup_dir)

                for table in drop_order:  # one statement per DROP: no shared transaction
                    connection.execute(f"DROP TABLE IF EXISTS {table}")
                existing = set()
            else:
                missing = sorted(expected_tables - existing)
                if existing and missing:
                    raise RuntimeError(
                        "The warehouse schema is incomplete and contains existing tables; "
                        f"run with full_rebuild=true to recreate it. Missing: {missing}"
                    )

            if not existing:
                connection.execute(schema_sql.read_text(encoding="utf-8"))
            connection.execute(dimensions_sql.read_text(encoding="utf-8"))
          
            duplicates = connection.execute(
                "SELECT count(*) FROM (SELECT cameo_code FROM dim_country "
                "GROUP BY 1 HAVING count(*) > 1)"
            ).fetchone()[0]
            if duplicates:
                raise RuntimeError(
                    f"dim_country inconsistent: {duplicates} duplicates"
                )

            drift = connection.execute(
                "SELECT count(*) FROM dim_country_source s "
                "JOIN dim_country t USING (cameo_code) "
                "WHERE t.iso3_code IS DISTINCT FROM s.iso3_code "
                "OR t.fips_code IS DISTINCT FROM s.fips_code"
            ).fetchone()[0]
            if drift:
                log.warning(
                    "%s countries have an iso3/fips code that differs from the source; "
                    "these indexed columns are not updated. Rerun with full_rebuild=true.",
                    drift,
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
