import json
from pathlib import Path

DEFAULT_QID_CACHE = Path(__file__).resolve().parents[2] / "data/cache/mediawiki_qids.json"


def load_qid_cache(path=DEFAULT_QID_CACHE):
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_qid_cache(cache, path=DEFAULT_QID_CACHE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
