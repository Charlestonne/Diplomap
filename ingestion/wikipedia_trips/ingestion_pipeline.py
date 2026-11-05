from .storage import save_raw_page, DEFAULT_OUTPUT
from .inventory import load_inventory, DEFAULT_INVENTORY
from .scraper import fetch_wikipedia_page
from .parser import get_year_tables, parse_table


# Extract diplomatic trips for a given leader and year from a Wikipedia page.
def extract_visits(page_title, leader, year):
    page = fetch_wikipedia_page(page_title)

    tables = get_year_tables(page["text"], year)

    visits = []

    for table in tables:
        rows = parse_table(table)

        for row in rows:
            visits.append({
                "leader": leader,
                "year": year,
                "host_country_raw": row["Country"],
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
