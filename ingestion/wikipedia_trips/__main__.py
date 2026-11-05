import argparse

from .ingestion_pipeline import extract_visits, extract_saved_visits, collect_pages
from .inventory import DEFAULT_INVENTORY
from .config import DEFAULT_ANALYSIS_CONFIG
from .storage import DEFAULT_OUTPUT, DEFAULT_DATE_NORMALIZED_OUTPUT
from .ingestion_pipeline import normalize_saved_visit_dates
from .qid_cache import DEFAULT_QID_CACHE


def main():
    parser = argparse.ArgumentParser(description="Wikipedia leaders trip ingestion")
    parser.add_argument("--collect", action="store_true", help="Save raw inventory pages without parsing")
    parser.add_argument("--inventory", default=DEFAULT_INVENTORY)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)

    parser.add_argument("--saved-page", help="Directory containing page.html and metadata.json")
    parser.add_argument("--leader", default="Emmanuel Macron")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--normalize", action="store_true", help="Normalize visit dates and filter by the configured analysis period")
    parser.add_argument("--normalized-output", default=DEFAULT_DATE_NORMALIZED_OUTPUT)
    parser.add_argument("--analysis-config", default=DEFAULT_ANALYSIS_CONFIG)
    parser.add_argument("--resolve-qids", action="store_true", help="Resolve host country QIDs using MediaWiki and a local cache")
    parser.add_argument("--qid-cache", default=DEFAULT_QID_CACHE)
    parser.add_argument("--refresh-qids", action="store_true", help="Refresh cached results for requested country names")
    args = parser.parse_args()
    if args.resolve_qids and not args.normalize:
        parser.error("--resolve-qids requires --normalize")
    if args.refresh_qids and not args.resolve_qids:
        parser.error("--refresh-qids requires --resolve-qids")
    if args.normalize and (not args.saved_page or args.collect):
        parser.error("--normalize requires --saved-page and cannot be combined with --collect")
    if args.collect:
        for path in collect_pages(args.inventory, args.output):
            print(path)
        return

    if args.normalize:
        summary = normalize_saved_visit_dates(
            args.saved_page, args.leader, args.year, args.normalized_output,
            analysis_config=args.analysis_config,
            resolve_qids=args.resolve_qids,
            qid_cache=args.qid_cache,
            refresh_qids=args.refresh_qids,
        )
        print(f"Extracted: {summary['extracted']}; kept: {summary['normalized']}; "
              f"anomalies: {summary['anomalies']}; outside scope: {summary['excluded']}")
        print(summary["output"])
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
