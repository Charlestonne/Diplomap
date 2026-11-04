from pathlib import Path
import yaml

DEFAULT_INVENTORY = Path(__file__).resolve().parents[2] / "ingestion/config/leaders.yaml"


def load_inventory(path=DEFAULT_INVENTORY):
    """Load the inventory of leaders and Wikipedia pages to scrape"""
    leaders = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(leaders, list) or not leaders:
        raise ValueError("Inventory must contain at least one leader")
    return leaders
