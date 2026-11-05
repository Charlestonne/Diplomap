import argparse

from .ingestion_pipeline import extract_visits, extract_saved_visits, collect_pages
from .inventory import DEFAULT_INVENTORY
from .storage import DEFAULT_OUTPUT


def main():
    parser = argparse.ArgumentParser(description="Wikipedia leaders trip ingestion")
    parser.add_argument("--collect", action="store_true", help="Save raw inventory pages without parsing")
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)

    parser.add_argument("--saved-page", help="Directory containing page.html and metadata.json")
    parser.add_argument("--leader", default="Emmanuel Macron")
    parser.add_argument("--year", type=int, default=2025)
    args = parser.parse_args()
    if args.collect:
        for path in collect_pages(args.inventory, args.output):
            print(path)
        return
    
    if args.saved_page:
        visits = extract_saved_visits(args.saved_page, args.leader, args.year)
    else:
        visits = extract_visits(
            page_title="List of international presidential trips made by Emmanuel Macron",
            leader=args.leader,
            year=args.year,
        )

    print(f"{len(visits)} lines extracted")
    for visit in visits[:5]:
        print(visit)


if __name__ == "__main__":
    main()
