"""Download one GDELT week and load its archives into raw staging."""

from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.sdk import DAG, Param, task
from pendulum import datetime

from assets import gdelt_landing


with DAG(
    dag_id="diplomap_ingest_gdelt",
    start_date=datetime(2024, 12, 17, tz="UTC"),
    schedule=None,
    catchup=False,
    params={
        "start_date": Param(
            "2024-12-17",
            type="string",
            format="date",
            description="First UTC day of the seven-day GDELT extraction window",
        )
    },
    tags=["diplomap", "ingestion"],
) as dag:
    start = EmptyOperator(task_id="start")

    @task
    def download_gdelt_week(start_date: str) -> None:
        from datetime import date, timedelta
        from pathlib import Path

        from ingestion.gdelt_events.spike_week import download_week, write_manifest

        output_dir = Path("/data/raw_landing/gdelt")
        first_day = date.fromisoformat(start_date)
        last_day = first_day + timedelta(days=6)
        rows = download_week(output_dir, first_day, last_day, overwrite=False)
        write_manifest(output_dir, rows)
        if not rows:
            raise RuntimeError(f"No GDELT export was found for {first_day}..{last_day}")
        failures = [row for row in rows if not row["integrity_ok"]]
        if failures:
            raise RuntimeError(f"{len(failures)} GDELT archive(s) failed integrity checks")

    @task(outlets=[gdelt_landing], pool="duckdb_writer")
    def load_gdelt_raw(start_date: str) -> None:
        import tempfile
        from datetime import date, timedelta
        from pathlib import Path

        import duckdb

        from warehouse.staging import load_gdelt_raw as loader

        raw_dir = Path("/data/raw_landing/gdelt")
        database = Path("/data/warehouse/diplomap.duckdb")
        first_day = date.fromisoformat(start_date)
        archives = []
        for offset in range(7):
            day_dir = raw_dir / (first_day + timedelta(days=offset)).isoformat()
            archives.extend(day_dir.glob("*.export.CSV.zip"))
        archives.sort()
        if not archives:
            raise RuntimeError(f"No GDELT archives found for {first_day}..{first_day + timedelta(days=6)}")

        database.parent.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(database)) as connection:
            loader.create_schema(connection)
            with tempfile.TemporaryDirectory(prefix="gdelt_load_") as temporary:
                for archive in archives:
                    loader.load_archive(connection, archive, Path(temporary))

    finish = EmptyOperator(task_id="finish")
    start >> download_gdelt_week("{{ params.start_date }}") >> load_gdelt_raw("{{ params.start_date }}") >> finish
