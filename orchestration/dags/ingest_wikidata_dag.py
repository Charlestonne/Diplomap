"""Airflow graph for the Wikidata leaders and countries pipeline"""

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import DAG, task
from pendulum import datetime

from assets import wikipedia_landing, wikidata_landing


with DAG(
    dag_id="diplomap_ingest_wikidata",
    start_date=datetime(2024, 12, 17, tz="UTC"),
    schedule=wikipedia_landing,
    catchup=False,
    tags=["diplomap", "ingestion", "wikidata"],
) as dag:
    start = EmptyOperator(task_id="start")

    @task
    def prepare_visit_input() -> str:
        import json
        from pathlib import Path

        wikipedia_root = Path("/data/date_normalized/wikipedia")
        visit_files = sorted(
            path
            for path in wikipedia_root.rglob("visits.json")
            if "qid_resolved" in path.parts and "_combined" not in path.parts
        )
        if not visit_files:
            raise RuntimeError("No QID-resolved Wikipedia visits found")

        visits_by_identity = {}
        for visits_file in visit_files:
            records = json.loads(visits_file.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                raise ValueError(f"Expected a JSON array in {visits_file}")
            for record in records:
                identity = (
                    record.get("wiki_page_id"),
                    record.get("wiki_revision_id"),
                    record.get("source_table_index"),
                    record.get("source_row_index"),
                )
                visits_by_identity[identity] = record

        combined_directory = wikipedia_root / "_combined" / "qid_resolved"
        combined_directory.mkdir(parents=True, exist_ok=True)
        visits_path = combined_directory / "visits.json"
        visits_path.write_text(
            json.dumps(list(visits_by_identity.values()), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return str(visits_path)

    @task
    def collect_raw_wikidata(visits_path: str) -> str:
        from pathlib import Path

        from ingestion.wikidata_leaders.ingestion_pipeline import collect_wikidata_from_visits

        collection = collect_wikidata_from_visits(
            visits_path,
            output=Path("/data/raw_landing/wikidata"),
            inventory=Path("/opt/diplomap/ingestion/config/leaders.yaml"),
        )
        return str(collection)

    @task
    def normalize_wikidata_collection(raw_collection_path: str) -> str:
        from pathlib import Path

        from ingestion.wikidata_leaders.ingestion_pipeline import normalize_saved_wikidata_collection

        collection = normalize_saved_wikidata_collection(
            raw_collection_path,
            output=Path("/data/normalized/wikidata"),
        )
        return str(collection)

    @task(outlets=[wikidata_landing])
    def resolve_wikidata_entities(normalized_collection_path: str, visits_path: str) -> str:
        from pathlib import Path

        from ingestion.wikidata_leaders.ingestion_pipeline import resolve_normalized_wikidata_collection

        collection = resolve_normalized_wikidata_collection(
            normalized_collection_path,
            visits_path,
            inventory=Path("/opt/diplomap/ingestion/config/leaders.yaml"),
            output=Path("/data/resolved/wikidata"),
        )
        return str(collection)

    finish = EmptyOperator(task_id="finish")
    visits = prepare_visit_input()
    raw_collection = collect_raw_wikidata(visits)
    normalized_collection = normalize_wikidata_collection(raw_collection)
    resolved_collection = resolve_wikidata_entities(normalized_collection, visits)
    start >> visits >> raw_collection >> normalized_collection >> resolved_collection >> finish
