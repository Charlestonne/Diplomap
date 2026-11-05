import os
import time

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import requests

API_URL = "https://en.wikipedia.org/w/api.php" # Wikimedia API endpoint

HEADERS = {
    "User-Agent": os.environ.get(
        "WIKIMEDIA_USER_AGENT", "DiplomaticTripsResearch/1.0 (local research script)"
    )
}


def fetch_wikipedia_page(page_title, language="en"):
    params = {
        "action": "parse",
        "page": page_title,
        "prop": "text|revid",
        "format": "json",
        "formatversion": 2
    }

    response = requests.get(
        f"https://{language}.wikipedia.org/w/api.php",
        params=params,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise RuntimeError(data["error"])

    return data["parse"]

def fetch_page_qids(page_titles, language="en", request_interval=1.0):
    """Resolve distinct titles in sequential batches, retaining every status"""
    results = {}
    unique_titles = list(dict.fromkeys(page_titles))
    if not unique_titles:
        return results
    if request_interval < 0:
        raise ValueError("Request interval cannot be negative")

    # Retry temporary HTTP failures
    retries = Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 503],
        respect_retry_after_header=True,
    )
    with requests.Session() as session:
        session.headers.update(HEADERS)
        session.mount("https://", HTTPAdapter(max_retries=retries))
        for offset in range(0, len(unique_titles), 50):
            if offset:
                time.sleep(request_interval)
            requested_titles = unique_titles[offset:offset + 50]
            response = session.get(
                f"https://{language}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "titles": "|".join(requested_titles),
                    "prop": "pageprops",
                    "ppprop": "wikibase_item|disambiguation",
                    "redirects": 1,
                    "format": "json",
                    "formatversion": 2,
                    "maxlag": 5,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                # API failures (including maxlag) must not become cached misses.
                raise RuntimeError(data["error"])
            results.update(parse_page_qids(data["query"], requested_titles))
    return results


def parse_page_qids(query, requested_titles):
    """Map normalized/redirected API titles back to the requested names."""
    title_changes = {
        change["from"]: change["to"]
        for change in query.get("normalized", []) + query.get("redirects", [])
    }
    pages_by_title = {page["title"]: page for page in query["pages"]}
    results = {}
    for requested_title in requested_titles:
        resolved_title = requested_title
        seen_titles = set()
        while resolved_title in title_changes and resolved_title not in seen_titles:
            seen_titles.add(resolved_title)
            resolved_title = title_changes[resolved_title]

        page = pages_by_title.get(resolved_title, {})
        properties = page.get("pageprops", {})
        qid = properties.get("wikibase_item")
        if not page or "missing" in page:
            status = "missing"
        elif "invalid" in page:
            status = "invalid_title"
        elif "disambiguation" in properties:
            status = "disambiguation"
        elif page.get("ns") != 0:
            status = "not_article"
        elif not qid:
            status = "no_qid"
        else:
            status = "resolved"
        results[requested_title] = {
            "qid": qid if status == "resolved" else None,
            "resolved_title": resolved_title,
            "status": status,
        }
    return results
