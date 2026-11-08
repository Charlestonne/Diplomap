import os
from pathlib import Path

import requests


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
QUERIES_DIRECTORY = Path(__file__).resolve().parent / "queries"


def load_query(query_filename):
    query_path = QUERIES_DIRECTORY / query_filename
    return query_path.read_text(encoding="utf-8")


def execute_query(query, endpoint=SPARQL_ENDPOINT, timeout=60):
    """Execute a SELECT or ASK query and return the complete JSON response"""
    if not any(line.strip() and not line.lstrip().startswith("#") for line in query.splitlines()):
        raise ValueError("SPARQL query is empty or contains comments only") # case of a draft query file

    response = requests.get(
        endpoint,
        params={"query": query},
        headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": os.environ.get(
                "WIKIMEDIA_USER_AGENT",
                "DiplomaticTripsResearch/1.0 (local research script)",
            ),
        },
        timeout=timeout,
    )
    response.raise_for_status() # HTTP errors are raised to the caller, never replaced with an empty result
    result = response.json()
    if not isinstance(result, dict) or not ("results" in result or "boolean" in result):
        raise ValueError("Unexpected SPARQL response: expected SELECT or ASK results")
    return result
