"""Airflow graph for the Wikidata leaders and countries pipeline"""

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import DAG
from pendulum import datetime

from assets import wikidata_landing


with DAG(
    dag_id="diplomap_ingest_wikidata",
    start_date=datetime(2024, 12, 17, tz="UTC"),
    schedule=None,
    catchup=False,
    tags=["diplomap", "ingestion", "wikidata"],
) as dag:
    start = EmptyOperator(task_id="start")
    load_visit_qids = EmptyOperator(task_id="load_visit_qids")
    query_countries = EmptyOperator(task_id="query_countries")
    query_leader_offices = EmptyOperator(task_id="query_leader_offices")
    persist_raw_responses = EmptyOperator(task_id="persist_raw_responses")
    normalize_responses = EmptyOperator(task_id="normalize_responses")
    resolve_countries = EmptyOperator(task_id="resolve_countries")
    resolve_office_periods = EmptyOperator(task_id="resolve_office_periods")
    check_quality = EmptyOperator(task_id="check_quality")
    publish_collection = EmptyOperator(
        task_id="publish_collection",
        outlets=[wikidata_landing],
    )
    finish = EmptyOperator(task_id="finish")

    (
        start
        >> load_visit_qids
        >> [query_countries, query_leader_offices]
        >> persist_raw_responses
        >> normalize_responses
        >> [resolve_countries, resolve_office_periods]
        >> check_quality
        >> publish_collection
        >> finish
    )
