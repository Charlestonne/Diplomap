"""Warehouse skeleton triggered only after all three landing assets are updated."""

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import DAG, task
from pendulum import datetime

from assets import gdelt_landing, wikidata_landing, wikipedia_landing


with DAG(
    dag_id="diplomap_build_warehouse",
    start_date=datetime(2024, 12, 17, tz="UTC"),
    schedule=[gdelt_landing, wikipedia_landing, wikidata_landing],
    catchup=False,
    tags=["diplomap", "warehouse"],
) as dag:
    start = EmptyOperator(task_id="start")

    @task(pool="duckdb_writer")
    def test_imports() -> None:
        import ingestion
        import warehouse

        assert ingestion is not None
        assert warehouse is not None

    staging = EmptyOperator(task_id="staging")
    production = EmptyOperator(task_id="production")
    serving = EmptyOperator(task_id="serving")

    start >> test_imports() >> staging >> production >> serving
