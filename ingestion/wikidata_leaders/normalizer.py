import re
from datetime import datetime


def binding_value(binding, variable):
    """Return the string value of a variable in a SPARQL binding or None if missing."""
    value = binding.get(variable)
    return None if value is None else value["value"]


def entity_qid(entity_uri):
    """Extract the QID from a wikidata entity URI"""
    match = re.fullmatch(r"https?://www\.wikidata\.org/entity/(Q[1-9][0-9]*)", entity_uri or "")
    if match is None:
        raise ValueError(f"Invalid Wikidata entity URI: {entity_uri!r}")
    return match[1]


def normalize_date(timestamp):
    """Convert a timestamp to an ISO date (missing dates remain None)"""
    if timestamp is None:
        return None
    # Keep the original timestamp in the normalized record for later review.
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()


def normalize_office_statement(binding):
    """One input binding remains one office statement row (not a validated mandate)"""
    statement_uri = binding_value(binding, "statement")
    if not statement_uri:
        raise ValueError("Missing office statement identifier")
    start_time = binding_value(binding, "start")
    end_time = binding_value(binding, "end")
    return {
        "leader_qid": entity_qid(binding_value(binding, "leader")),
        "leader_name": binding_value(binding, "leaderLabel"),
        "statement_uri": statement_uri,
        "position_qid": entity_qid(binding_value(binding, "position")),
        "position_title": binding_value(binding, "positionLabel"),
        "start_date": normalize_date(start_time),
        "end_date": normalize_date(end_time),
        "start_time_raw": start_time,
        "end_time_raw": end_time,
    }


def normalize_country(binding):
    """Keep every returned country row including rows with missing codes"""
    return {
        "country_qid": entity_qid(binding_value(binding, "country")),
        "country_name": binding_value(binding, "countryLabel"),
        "iso3_code": binding_value(binding, "iso3"),
        "fips_code": binding_value(binding, "fips"),
    }


def normalize_response(response, family, source):
    """Normalize bindings independently and preserve unreadable ones for review"""
    normalizers = {"leaders": normalize_office_statement, "countries": normalize_country}
    normalize_binding = normalizers[family]
    bindings = response["results"]["bindings"]
    if not isinstance(bindings, list):
        raise ValueError("SPARQL results.bindings must be a list")

    normalized_rows = []
    review_items = []
    
    for binding_index, binding in enumerate(bindings, start=1):
        provenance = {**source, "source_binding_index": binding_index}
        try:
            normalized_rows.append({**normalize_binding(binding), **provenance})
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            review_items.append({
                **provenance,
                "family": family,
                "error_code": "invalid_wikidata_binding",
                "error_reason": str(error),
                "raw_binding": binding,
            })
    return normalized_rows, review_items
