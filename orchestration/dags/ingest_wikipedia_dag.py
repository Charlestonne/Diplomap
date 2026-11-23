"""Airflow graph for the Wikipedia diplomatic-trips pipeline"""

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import DAG, task
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

    @task
    def load_inventory_task() -> str:
        from pathlib import Path

        from ingestion.wikipedia_trips.inventory import load_inventory

        inventory_path = Path("/opt/diplomap/ingestion/config/leaders.yaml")
        load_inventory(inventory_path)
        return str(inventory_path)

    @task
    def collect_wikipedia_pages(inventory_path: str) -> list[str]:
        from pathlib import Path

        from ingestion.wikipedia_trips.ingestion_pipeline import collect_pages

        return [
            str(path)
            for path in collect_pages(
                Path(inventory_path),
                Path("/data/raw_landing/wikipedia"),
            )
        ]

    @task(outlets=[wikipedia_landing])
    def process_wikipedia_pages(saved_pages: list[str], inventory_path: str) -> list[str]:
        from pathlib import Path

        from ingestion.wikipedia_trips.ingestion_pipeline import (
            normalize_saved_visit_dates,
        )
        from ingestion.wikipedia_trips.inventory import find_leader, load_inventory
        from ingestion.wikipedia_trips.storage import load_raw_page

        inventory_file = Path(inventory_path)
        analysis_path = Path("/opt/diplomap/ingestion/config/analysis.yaml")
        normalized_root = Path("/data/date_normalized/wikipedia")
        qid_cache = Path("/data/cache/mediawiki_qids.json")

        leaders = load_inventory(inventory_file)
        summaries = []
        for page_path in saved_pages:
            page_directory = Path(page_path)
            page = load_raw_page(page_directory)
            leader = find_leader(page["leader_local_id"], inventory_file)
            matching_sources = [
                source
                for source in leader["trips_pages"]
                if source["language"] == page["language"]
                and source["title"] == page["page_title"]
            ]
            if not matching_sources:
                raise ValueError(f"No inventory source matches {page_directory}")
            for source in matching_sources:
                for year in source.get("years", []):
                    summary = normalize_saved_visit_dates(
                        page_directory,
                        leader["leader_id"],
                        year,
                        output=normalized_root,
                        analysis_config=analysis_path,
                        resolve_qids=True,
                        qid_cache=qid_cache,
                        inventory=inventory_file,
                        include_multilateral=True,
                    )
                    summaries.append(str(summary["output"]))
        if not leaders or not summaries:
            raise RuntimeError("Wikipedia pipeline produced no normalized visit collection")
        return summaries

    finish = EmptyOperator(task_id="finish")
    inventory = load_inventory_task()
    saved_pages = collect_wikipedia_pages(inventory)
    processed_pages = process_wikipedia_pages(saved_pages, inventory)
    
    start >> inventory >> saved_pages >> processed_pages >> finish
