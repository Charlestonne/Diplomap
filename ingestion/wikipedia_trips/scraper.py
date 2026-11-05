import os
import time
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
