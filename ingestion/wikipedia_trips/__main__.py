import argparse

from .ingestion_pipeline import extract_visits, collect_pages
from .inventory import DEFAULT_INVENTORY
from .storage import DEFAULT_OUTPUT


def main():
    parser = argparse.ArgumentParser(description="Wikipedia leaders trip ingestion")
    parser.add_argument("--collect", action="store_true", help="Save raw inventory pages without parsing")
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)

    args = parser.parse_args()
    if args.collect:
        for path in collect_pages(args.inventory, args.output):
            print(path)
        return
    
    visits = extract_visits(
        page_title=("List of international presidential trips made by Emmanuel Macron"),
        leader="Emmanuel Macron",
        year=2025,
    )

    print(f"{len(visits)} lines extractd")
    for visit in visits[:5]:
        print(visit)


if __name__ == "__main__":
    main()
