

def is_valid_country_code(code, expected_length):
    """Require the expected number of uppercase ASCII letters"""
    return (
        isinstance(code, str)
        and len(code) == expected_length
        and code.isascii()
        and code.isupper()
        and code.isalpha()
    )


def check_country_code_formats(countries):
    """ISO3 is required
    FIPS may be absent but must be valid if provided, same for CAMEO (optional)"""
    issues = []
    for country in countries:
        if not is_valid_country_code(country["iso3_code"], 3):
            issues.append({
                "severity": "error", "code": "missing_or_invalid_iso3",
                "reason": "A valid ISO3 is required by dim_country", "record": country,
            })
        fips_code = country["fips_code"]
        if fips_code is not None and not is_valid_country_code(fips_code, 2):
            issues.append({
                "severity": "error", "code": "invalid_fips",
                "reason": "FIPS must be absent or two uppercase letters", "record": country,
            })
        cameo_code = country.get("cameo_code")
        if cameo_code is not None and not is_valid_country_code(cameo_code, 3):
            issues.append({
                "severity": "error", "code": "invalid_cameo",
                "reason": "CAMEO must be absent or three uppercase letters", "record": country,
            })
    return issues


def check_shared_country_codes(countries):
    """A code must not be assigned to several country QIDs"""
    issues = []
    for field in ("iso3_code", "fips_code", "cameo_code"):
        code_owners = {}
        for country in countries:
            code = country.get(field)
            if code:
                code_owners.setdefault(code, set()).add(country["country_qid"])
        for code, country_qids in code_owners.items():
            if len(country_qids) > 1:
                issues.append({
                    "severity": "error", "code": "conflicting_country_code",
                    "reason": f"{field} {code!r} belongs to several QIDs",
                    "country_qids": sorted(country_qids),
                })
    return issues


def check_represented_countries(countries, visits):
    """The reference must include origins as well as destinations"""
    collected_iso3 = {country["iso3_code"] for country in countries}
    represented_iso3 = {
        visit["visitor_country_iso3"] for visit in visits if visit.get("visitor_country_iso3")
    }
    issues = []
    for iso3_code in sorted(represented_iso3):
        if iso3_code not in collected_iso3:
            issues.append({
                "severity": "error", "code": "missing_visitor_country_reference",
                "reason": "Represented country must also be collected before loading the warehouse",
                "iso3_code": iso3_code,
            })
    return issues


def check_visit_countries(countries, visits):
    """Check known host QIDs and ensure visitors and hosts are different."""
    countries_by_qid = {}
    for country in countries:
        countries_by_qid.setdefault(country["country_qid"], []).append(country)

    issues = []
    for visit in visits:
        host_qid = visit.get("host_country_qid")
        host_countries = countries_by_qid.get(host_qid, [])
        if not host_qid or not host_countries:
            issues.append({
                "severity": "error", "code": "unknown_host_country",
                "reason": "Host country QID is absent from collected countries", "record": visit,
            })
        visitor_iso3 = visit.get("visitor_country_iso3")
        if visitor_iso3 and any(host["iso3_code"] == visitor_iso3 for host in host_countries):
            issues.append({
                "severity": "error", "code": "same_visitor_and_host",
                "reason": "Visitor and host country must differ", "record": visit,
            })
    return issues


def check_country_references(countries, visits):
    """Collect independent country checks; no rows are modified or removed."""
    issues = check_country_code_formats(countries)
    issues.extend(check_shared_country_codes(countries))
    issues.extend(check_represented_countries(countries, visits))
    issues.extend(check_visit_countries(countries, visits))
    return issues
