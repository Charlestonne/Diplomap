from .country_checks import check_country_code_formats, check_shared_country_codes


def group_country_rows(countries):
    """Group collected country rows by QID, including those with missing codes."""
    grouped = {}
    for country in countries:
        grouped.setdefault(country["country_qid"], []).append(country)
    return grouped


def merge_country_rows(country_qid, rows):
    """Merge compatible Wikidata rows without supplying missing values"""
    country = {"country_qid": country_qid, "source_records": rows}
    for field in ("country_name", "iso3_code", "fips_code"):
        values = {row[field] for row in rows if row.get(field) is not None}
        if len(values) > 1:
            raise ValueError(f"Conflicting {field} values for {country_qid}: {sorted(values)}")
        country[field] = next(iter(values), None)
    if not country["country_name"]:
        raise ValueError(f"Missing country name for {country_qid}")
    return country


def build_country_reference(countries):
    """Group and validate collected countries (missing codes remain missing)"""
    grouped = group_country_rows(countries)
    reference = []
    issues = []
    for country_qid, rows in sorted(grouped.items()):
        try:
            reference.append(merge_country_rows(country_qid, rows))
        except ValueError as error:
            issues.append({"severity": "error", "code": "invalid_country_reference",
                           "reason": str(error), "country_qid": country_qid,
                           "source_records": rows})
    issues.extend(check_country_code_formats(reference))
    issues.extend(check_shared_country_codes(reference))
    blocked_qids = set()
    for issue in issues:
        blocked_qids.update(issue.get("country_qids", []))
        if issue.get("record"):
            blocked_qids.add(issue["record"]["country_qid"])
    for country in reference:
        country["reference_status"] = "needs_review" if country["country_qid"] in blocked_qids else "checked"
    return reference, issues


def unique_country_index(countries, field):
    """Index only unambiguous identifiers (conflicting countries remain unresolved for the moemtn)"""
    grouped = {}
    for country in countries:
        value = country.get(field)
        if value:
            grouped.setdefault(value, []).append(country)
    return {value: rows[0] for value, rows in grouped.items() if len(rows) == 1}


def resolve_visit_countries(visits, countries):
    """Join hosts by QID and represented countries by ISO3, retaining every visit"""
    checked = [country for country in countries if country["reference_status"] == "checked"]
    by_qid = unique_country_index(checked, "country_qid")
    by_iso3 = unique_country_index(checked, "iso3_code")
    resolved_visits = []
    issues = []
    for visit in visits:
        resolved = {**visit, "country_resolution_status": "needs_review"}
        host = by_qid.get(visit.get("host_country_qid"))
        visitor = by_iso3.get(visit.get("visitor_country_iso3"))
        if host is None or visitor is None or not host.get("iso3_code"):
            issues.append({"severity": "error", "code": "unresolved_visit_countries",
                           "reason": "Expected one host QID and one represented ISO3 in the country reference",
                           "record": visit})
        else:
            for role, country in (("host", host), ("visitor", visitor)):
                for field, suffix in (
                    ("country_qid", "country_qid"), ("country_name", "country_name"),
                    ("iso3_code", "country_iso3"), ("fips_code", "country_fips"),
                ):
                    resolved[f"{role}_{suffix}"] = country[field]
            resolved["country_resolution_status"] = "resolved"
        resolved_visits.append(resolved)
    return resolved_visits, issues
