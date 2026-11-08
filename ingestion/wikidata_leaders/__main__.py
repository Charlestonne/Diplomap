import argparse

from .client import SPARQL_ENDPOINT
from .ingestion_pipeline import collect_wikidata_from_visits
from .storage import DEFAULT_OUTPUT


def main():
    # run with e.g. `python -m ingestion.wikidata_leaders --visits data/processed/visits.json --output data/raw_landing/wikidata`
    argument_parser = argparse.ArgumentParser(description="Collect raw Wikidata data for resolved visits")
    argument_parser.add_argument("--visits", required=True, help="Wikipedia visit JSON containing leader_qid and host_country_qid")
    argument_parser.add_argument("--output", default=DEFAULT_OUTPUT)
    argument_parser.add_argument("--batch-size", type=int, default=50)
    argument_parser.add_argument("--request-interval", type=float, default=1.0)
    argument_parser.add_argument("--endpoint", default=SPARQL_ENDPOINT)
    arguments = argument_parser.parse_args()
    if arguments.batch_size < 1 or arguments.request_interval < 0:
        argument_parser.error("--batch-size must be positive and --request-interval nonnegative")

    directory = collect_wikidata_from_visits(
        arguments.visits, output=arguments.output, batch_size=arguments.batch_size,
        request_interval=arguments.request_interval, endpoint=arguments.endpoint,
    )
    print(f"Wikidata collection saved to {directory}")


if __name__ == "__main__":
    main()
