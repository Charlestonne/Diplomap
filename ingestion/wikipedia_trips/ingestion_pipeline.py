from datetime import date
from pathlib import Path

from .storage import save_raw_page, load_raw_page, DEFAULT_OUTPUT
from .inventory import load_inventory, DEFAULT_INVENTORY
from .scraper import fetch_wikipedia_page
from .parser import get_year_tables, parse_table
from .normalizer import normalize_visit
from .config import load_analysis_period, DEFAULT_ANALYSIS_CONFIG
from .storage import save_date_normalized_visits, DEFAULT_DATE_NORMALIZED_OUTPUT


# Extract diplomatic trips for a given leader and year from a Wikipedia page.
def extract_visits(page_title, leader, year):
    page = fetch_wikipedia_page(page_title)
    return extract_page_visits(page, leader, year)


def extract_saved_visits(directory, leader, year):
    """Extract visits from locally saved captures"""
    return extract_page_visits(load_raw_page(directory), leader, year)


def extract_page_visits(page, leader, year):
    """Extract raw visit records from an already loaded page"""
    tables = get_year_tables(page["text"], year)

    visits = []

    for table in tables:
        rows = parse_table(table)

        for row in rows:
            visits.append({
                "leader": leader,
                "year": year,
                "host_country_raw": row["Country"],
                "host_country_link": row["country_link"],
                "wiki_language": page.get("language", "en"),
                "areas_visited_raw": row["Areas visited"],
                "date_raw": row["Date(s)"],
                "details_raw": row["Details"],
                "wiki_page_id": page["pageid"],
                "wiki_revision_id": page["revid"]
            })

    return visits

# Save the raw source pages before any parsing.
def collect_pages(inventory=DEFAULT_INVENTORY, output=DEFAULT_OUTPUT):
    paths = []
    for leader in load_inventory(inventory):
        for source in leader["trips_pages"]:
            page = fetch_wikipedia_page(source["title"], language=source["language"])
            path = save_raw_page(leader["leader_id"], source, page, output)
            paths.append(path)
    return paths


def normalize_and_filter_visit_dates(raw_visits, analysis_start, analysis_end):
    """Normalize dates and select visits starting within the inclusive period"""
    visits = []
    anomalies = []
    excluded_count = 0
    for raw_visit in raw_visits:
        try:
            normalized_visit = normalize_visit(raw_visit)
        except (ValueError, TypeError, IndexError) as error:
            anomalies.append({
                **raw_visit,
                "error_code": "invalid_visit_date",
                "error_reason": str(error),
            })
            continue

        visit_start = date.fromisoformat(normalized_visit["start_date"])
        if analysis_start <= visit_start <= analysis_end:
            visits.append(normalized_visit)
        else:
            excluded_count += 1
    return visits, anomalies, excluded_count


def normalize_saved_visit_dates(
    directory, leader, year, output=DEFAULT_DATE_NORMALIZED_OUTPUT,
    analysis_config=DEFAULT_ANALYSIS_CONFIG,
):
    """Extract a saved page, normalize dates, filter and persist the results"""
    analysis_start, analysis_end = load_analysis_period(analysis_config)
    page = load_raw_page(directory)
    raw_visits = extract_page_visits(page, leader, year)
    visits, anomalies, excluded_count = normalize_and_filter_visit_dates(
        raw_visits, analysis_start, analysis_end
    )
    # Separate captures and extraction years to avoid mixing their results.
    destination = (
        Path(output) / page["language"] / str(page["pageid"])
        / str(page["revid"]) / str(year)
        / f"{analysis_start}_{analysis_end}"
    )
    save_date_normalized_visits(visits, anomalies, destination)
    return {
        "output": destination,
        "extracted": len(raw_visits),
        "normalized": len(visits),
        "anomalies": len(anomalies),
        "excluded": excluded_count,
    }
