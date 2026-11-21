"""Airflow graph for the Wikipedia diplomatic-trips pipeline"""

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import DAG
from pendulum import datetime

from assets import wikipedia_landing


with DAG(
    dag_id="diplomap_ingest_wikipedia",
    start_date=datetime(2024, 12, 17, tz="UTC"),
    schedule=None,
    catchup=False,
    tags=["diplomap", "ingestion", "wikipedia"],
) as dag:
    start = EmptyOperator(task_id="start")
    load_inventory = EmptyOperator(task_id="load_inventory")
    collect_pages = EmptyOperator(task_id="collect_pages")
    parse_trip_tables = EmptyOperator(task_id="parse_trip_tables")
    normalize_dates = EmptyOperator(task_id="normalize_dates")
    resolve_qids = EmptyOperator(task_id="resolve_qids")
    enrich_multilateral = EmptyOperator(task_id="enrich_multilateral")
    publish_collection = EmptyOperator(
        task_id="publish_collection",
        outlets=[wikipedia_landing],
    )
    finish = EmptyOperator(task_id="finish")

    (
        start
        >> load_inventory
        >> collect_pages
        >> parse_trip_tables
        >> normalize_dates
        >> resolve_qids
        >> enrich_multilateral
        >> publish_collection
        >> finish
    )
