from datetime import date
from pathlib import Path

import yaml

DEFAULT_ANALYSIS_CONFIG = Path(__file__).resolve().parents[2] / "ingestion/config/analysis.yaml"


def load_analysis_period(path=DEFAULT_ANALYSIS_CONFIG):
    """Read the analysis period shared by visit date filtering"""
    settings = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    start_date = date.fromisoformat(str(settings["start_date"]))
    end_date = date.fromisoformat(str(settings["end_date"]))
    if end_date < start_date:
        raise ValueError("Analysis end date precedes start date")
    return start_date, end_date
