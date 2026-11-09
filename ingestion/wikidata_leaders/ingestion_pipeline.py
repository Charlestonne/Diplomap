import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .client import SPARQL_ENDPOINT, execute_query, load_query
from .storage import (
    DEFAULT_OUTPUT,
    create_collection_directory,
    save_collection_manifest,
    save_query_response,
    DEFAULT_NORMALIZED_OUTPUT,
    load_saved_query_response,
    save_normalized_collection,
)
from .normalizer import normalize_response
from ..wikipedia_trips.inventory import load_inventory, DEFAULT_INVENTORY
from .office_resolution import (
    resolve_leader_scope, select_office_periods, check_office_overlaps,
    resolve_visit_offices,
)
from .country_checks import check_represented_countries, check_visit_countries
from .country_resolution import (
    build_country_reference, resolve_visit_countries,
)
from .visit_checks import finalize_visit_resolution
from .storage import DEFAULT_RESOLVED_OUTPUT, load_normalized_collection, save_resolution_results


def extract_distinct_qids(visits, field):
    qids = set()  # deduplicate valid QIDs; sorted below for deterministic ordering
    for row_index, visit in enumerate(visits, start=1):
        qid = visit.get(field)
        if qid is None or qid == "":
            continue  # skip unresolved identifiers
        if not isinstance(qid, str) or re.fullmatch(r"Q[1-9][0-9]*", qid) is None:
            # reject invalid QIDs, reporting the row number
            raise ValueError(f"Invalid {field} in visit row {row_index}: {qid!r}")
        qids.add(qid)
    return sorted(qids)


def load_visits_with_provenance(visits_path):
    """Read enriched visits and identify the exact source file"""
    source_path = Path(visits_path).resolve()
    source_bytes = source_path.read_bytes()
    visits = json.loads(source_bytes)
    if not isinstance(visits, list) or any(
        not isinstance(visit, dict) for visit in visits
    ):
        raise ValueError("Expected a JSON list of visit records")
    if any(
        "leader_qid" not in visit or "host_country_qid" not in visit for visit in visits
    ):
        raise ValueError(
            "Use visits enriched with leader_qid and host_country_qid; unresolved values may be null"
        )

    source_provenance = {
        "source_visits": str(source_path),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
    }
    return visits, source_provenance


def prepare_query_batches(qids_by_family, batch_size):
    """Render all leader/country queries before starting collection"""
    batches = []
    for family, qids in qids_by_family.items():
        for offset in range(0, len(qids), batch_size):
            batch_qids = qids[offset : offset + batch_size]
            batches.append(
                {
                    "family": family,
                    "batch_number": offset // batch_size + 1,
                    "qids": batch_qids,
                    "query": load_query(f"{family}.sparql", batch_qids),
                }
            )
    return batches


def build_collection_manifest(visits, qids_by_family, provenance, batch_count):
    """Describe the input, requested QIDs and initial collection progress"""
    return {
        **provenance,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "visit_count": len(visits),
        "leader_qids": qids_by_family["leaders"],
        "country_qids": qids_by_family["countries"],
        "visits_without_leader_qid": sum(
            not visit.get("leader_qid") for visit in visits
        ),
        "visits_without_country_qid": sum(
            not visit.get("host_country_qid") for visit in visits
        ),
        "planned_batches": batch_count,
        "completed_batches": [],
    }


def collect_query_batches(batches, directory, provenance, manifest, request_interval):
    """Fetch and save each batch, updating the manifest after every success"""
    for batch_index, batch in enumerate(batches):
        if batch_index:
            time.sleep(request_interval)
        response = execute_query(batch["query"], endpoint=provenance["endpoint"])
        relative_directory = f"{batch['family']}/{batch['batch_number']:03d}"
        metadata = {
            **provenance,
            "query_file": f"{batch['family']}.sparql",
            "requested_qids": batch["qids"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        save_query_response(
            response, batch["query"], metadata, directory / relative_directory
        )
        manifest["completed_batches"].append(relative_directory)
        save_collection_manifest(manifest, directory)


def extract_country_qids(visits, inventory):
    """Collect both host countries and the configured countries represented by leaders"""
    leader_ids = {visit.get("leader_local_id") for visit in visits}
    countries = [{"country_qid": qid} for qid in extract_distinct_qids(visits, "host_country_qid")]
    configured_ids = set()
    for leader in inventory:
        if leader["leader_id"] not in leader_ids:
            continue
        if not leader.get("represented_country_qid"):
            raise ValueError(f"Configure represented_country_qid for {leader['leader_id']}")
        configured_ids.add(leader["leader_id"])
        countries.append({"country_qid": leader["represented_country_qid"]})
    if leader_ids - configured_ids:
        raise ValueError("Every visit needs a leader_local_id present in the inventory")
    return extract_distinct_qids(countries, "country_qid")


def collect_wikidata_from_visits(
    visits_path,
    output=DEFAULT_OUTPUT,
    batch_size=50,
    request_interval=1.0,
    endpoint=SPARQL_ENDPOINT,
    inventory=DEFAULT_INVENTORY,
):
    """Coordinate input reading, batch preparation, collection and final status"""
    if batch_size < 1 or request_interval < 0:
        raise ValueError("Batch size must be positive and request interval nonnegative")

    visits, source_provenance = load_visits_with_provenance(visits_path)
    qids_by_family = {
        "leaders": extract_distinct_qids(visits, "leader_qid"),
        "countries": extract_country_qids(visits, load_inventory(inventory)),
    }
    batches = prepare_query_batches(qids_by_family, batch_size)

    directory = create_collection_directory(output)
    provenance = {
        **source_provenance, "endpoint": endpoint,
        "inventory": str(Path(inventory).resolve()),
        "inventory_sha256": hashlib.sha256(Path(inventory).read_bytes()).hexdigest(),
    }
    manifest = build_collection_manifest(
        visits, qids_by_family, provenance, len(batches)
    )
    save_collection_manifest(manifest, directory)

    try:
        collect_query_batches(
            batches, directory, provenance, manifest, request_interval
        )
    except Exception as error:
        # Preserve successful batches, but never present a partial run as complete.
        manifest["status"] = "failed"
        manifest["error"] = str(error)
        save_collection_manifest(manifest, directory)
        raise

    manifest["status"] = "complete"
    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    save_collection_manifest(manifest, directory)
    return directory


def normalize_saved_wikidata_collection(collection_path, output=DEFAULT_NORMALIZED_OUTPUT):
    """Normalize a previously completed collection without calling the SPARQL endpoint"""
    collection_directory = Path(collection_path).resolve()
    collection_manifest = json.loads(
        (collection_directory / "manifest.json").read_text(encoding="utf-8")
    )
    if collection_manifest["status"] != "complete":
        raise ValueError("Normalize a complete collection, not a failed or interrupted run")
    completed_batches = collection_manifest["completed_batches"]
    if (len(completed_batches) != collection_manifest["planned_batches"]
            or len(set(completed_batches)) != len(completed_batches)):
        raise ValueError("Collection manifest has an inconsistent batch count")

    records = {"leaders": [], "countries": []}
    review_items = []
    for batch_directory in completed_batches:
        if re.fullmatch(r"(leaders|countries)/[0-9]{3,}", batch_directory) is None:
            raise ValueError(f"Unrecognized collection batch: {batch_directory!r}")
        family = batch_directory.split("/")[0]
        directory = collection_directory / batch_directory
        response, metadata = load_saved_query_response(directory)
        source = {
            "source_response": str(directory / "response.json"),
            "source_query": str(directory / "query.sparql"),
            "fetched_at": metadata["fetched_at"],
        }
        normalized_rows, batch_issues = normalize_response(response, family, source)
        records[family].extend(normalized_rows)
        review_items.extend(batch_issues)

    manifest = {
        "source_collection": str(collection_directory),
        "normalized_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete_with_issues" if review_items else "complete",
        "office_statement_count": len(records["leaders"]),
        "country_row_count": len(records["countries"]),
        "issue_count": len(review_items),
    }
    destination = Path(output) / collection_directory.name
    if destination.resolve() == collection_directory:
        raise ValueError("Normalized output must not overwrite the raw collection")
    save_normalized_collection(records, review_items, manifest, destination)
    return destination


def resolve_visit_entities(visits, normalized, inventory):
    """Match offices and countries then collect visit and source issues in memory"""
    scope = resolve_leader_scope(visits, inventory)
    periods, unselected, issues = select_office_periods(normalized["office_statements"], scope)
    issues.extend(check_office_overlaps(periods))
    resolved_visits, visit_issues = resolve_visit_offices(visits, periods)
    issues.extend(visit_issues)
    reference, reference_issues = build_country_reference(normalized["countries"])
    issues.extend(reference_issues)
    resolved_visits, country_issues = resolve_visit_countries(resolved_visits, reference)
    issues.extend(country_issues)
    issues.extend(check_represented_countries(reference, resolved_visits))
    issues.extend(check_visit_countries(reference, resolved_visits))
    resolved_visits, final_issues = finalize_visit_resolution(resolved_visits, periods)
    issues.extend(final_issues)
    issues.extend(
        {"severity": "error", "code": "source_normalization_issue", "details": issue}
        for issue in normalized["normalization_issues"]
    )
    return {
        "office_periods": periods,
        "visits": resolved_visits,
        "unselected_office_statements": unselected,
        "resolution_issues": issues,
        "countries": reference,
        "unresolved_visits": [visit for visit in resolved_visits if visit["resolution_status"] != "resolved"],
    }


def build_resolution_manifest(results, directory, visit_source, inventory):
    """Summarize resolution counts and record the source provenance"""
    resolved_visits = results["visits"]
    issues = results["resolution_issues"]
    return {
        "source_collection": str(directory), **visit_source,
        "inventory": str(Path(inventory).resolve()),
        "inventory_sha256": hashlib.sha256(Path(inventory).read_bytes()).hexdigest(),
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "status": "needs_review" if any(issue["severity"] == "error" for issue in issues) else "checked",
        "selected_office_periods": len(results["office_periods"]),
        "unselected_office_statements": len(results["unselected_office_statements"]),
        "visit_count": len(resolved_visits),
        "visits_with_unique_office": sum(visit["office_resolution_status"] == "resolved" for visit in resolved_visits),
        "resolved_visit_count": sum(visit["resolution_status"] == "resolved" for visit in resolved_visits),
        "unresolved_visit_count": sum(visit["resolution_status"] != "resolved" for visit in resolved_visits),
        "country_count": len(results["countries"]),
        "errors": sum(issue["severity"] == "error" for issue in issues),
        "warnings": sum(issue["severity"] == "warning" for issue in issues),
        "end_date_policy": "missing_end_is_open_with_explicit_status",
        "stage": "entity_resolution_not_warehouse_loading",
    }


def resolve_normalized_wikidata_collection(
    collection_path, visits_path, inventory=DEFAULT_INVENTORY, output=DEFAULT_RESOLVED_OUTPUT,
):
    """Load inputs, resolve visit entities and save the results separately"""
    directory = Path(collection_path).resolve()
    destination = Path(output) / directory.name
    if destination.resolve() == directory:
        raise ValueError("Resolution output must not overwrite normalized input")

    normalized = load_normalized_collection(directory)
    visits, visit_source = load_visits_with_provenance(visits_path)
    results = resolve_visit_entities(visits, normalized, load_inventory(inventory))
    results["manifest"] = build_resolution_manifest(results, directory, visit_source, inventory)
    save_resolution_results(results, destination)
    return destination
