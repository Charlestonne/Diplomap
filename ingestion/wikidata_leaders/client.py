import os
import re
from pathlib import Path

import requests


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
QUERIES_DIRECTORY = Path(__file__).resolve().parent / "queries"
QIDS_PLACEHOLDER = "{{QIDS}}"


def load_query(query_filename, qids):
    """Read a query template and fill its VALUES block with validated QIDs"""
    if isinstance(qids, str):
        raise ValueError("Pass QIDs as a collection, not a single string")
    unique_qids = list(dict.fromkeys(qids))
    if not unique_qids:
        raise ValueError("At least one QID is required")
    for qid in unique_qids:
        if not isinstance(qid, str) or re.fullmatch(r"Q[1-9][0-9]*", qid) is None:
            raise ValueError(f"Invalid Wikidata QID: {qid!r}")

    query_path = QUERIES_DIRECTORY / query_filename
    query_template = query_path.read_text(encoding="utf-8")
    if query_template.count(QIDS_PLACEHOLDER) != 1:
        raise ValueError("Query template must contain exactly one {{QIDS}} placeholder")

    entity_values = " ".join(f"wd:{qid}" for qid in unique_qids)
    return query_template.replace(QIDS_PLACEHOLDER, entity_values)


def execute_query(query, endpoint=SPARQL_ENDPOINT, timeout=60):
    """Execute a SELECT or ASK query and return the complete JSON response"""
    if not any(line.strip() and not line.lstrip().startswith("#") for line in query.splitlines()):
        raise ValueError("SPARQL query is empty or contains comments only") # case of a draft query file
    if QIDS_PLACEHOLDER in query:
        raise ValueError("Fill query parameters with load_query(filename, qids) before execution")

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
