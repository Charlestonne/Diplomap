from pathlib import Path
import yaml

DEFAULT_INVENTORY = Path(__file__).resolve().parents[2] / "ingestion/config/leaders.yaml"


def load_inventory(path=DEFAULT_INVENTORY):
    """Load the inventory of leaders and Wikipedia pages to scrape"""
    leaders = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(leaders, list) or not leaders:
        raise ValueError("Inventory must contain at least one leader")
    return leaders


def find_leader(leader_name_or_id, path=DEFAULT_INVENTORY):
    """Find exactly one configured leader by local identifier or name."""
    matches = []
    for leader in load_inventory(path):
        if leader_name_or_id in (leader["leader_id"], leader["leader_name"]):
            matches.append(leader)
    if len(matches) != 1:
        raise ValueError(f"Expected one leader in inventory for {leader_name_or_id!r}, found {len(matches)}")
    return matches[0]
