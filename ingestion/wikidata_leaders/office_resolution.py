from datetime import date


def resolve_leader_scope(visits, inventory):
    """Link each leader QID to its configured offices and represented country"""
    leader_scope = {}
    for leader in inventory:
        leader_qids = {
            visit["leader_qid"] for visit in visits
            if visit.get("leader_local_id") == leader["leader_id"] and visit.get("leader_qid")
        }
        if len(leader_qids) > 1:
            raise ValueError(f"Several QIDs refer to local leader {leader['leader_id']!r}")
        if not leader_qids:
            continue
        if not leader.get("position_qids") or not leader.get("represented_country_iso3"):
            raise ValueError(f"Configure position_qids and represented_country_iso3 for {leader['leader_id']}")
        leader_qid = next(iter(leader_qids))
        leader_scope[leader_qid] = leader
    return leader_scope


def build_office_period(statement, leader):
    """Validate dates and attach the configured country to one source statement"""
    start_date = date.fromisoformat(statement["start_date"])
    end_date = None
    if statement["end_date"] is not None:
        end_date = date.fromisoformat(statement["end_date"])
    if end_date is not None and end_date < start_date:
        raise ValueError("Office end date precedes start date")

    return {
        **statement,
        "leader_local_id": leader["leader_id"],
        "represented_country_iso3": leader["represented_country_iso3"],
        "represented_country_source": "leader_inventory",
        "valid_from": start_date.isoformat(),
        "valid_to": end_date.isoformat() if end_date is not None else None,
        "end_date_status": "reported" if end_date is not None else "not_reported_open_interval",
    }


def select_office_periods(office_statements, leader_scope):
    """Keep selected periods, unselected source statements and issues separately"""
    periods = []
    unselected = []
    issues = []
    for statement in office_statements:
        leader = leader_scope.get(statement["leader_qid"])
        if leader is None or statement["position_qid"] not in leader["position_qids"]:
            unselected.append({**statement, "selection_reason": "outside_configured_office_scope"})
            continue
        try:
            period = build_office_period(statement, leader)
        except (ValueError, TypeError, KeyError) as error:
            issues.append({
                "severity": "error", "code": "invalid_office_dates",
                "reason": str(error), "record": statement,
            })
            continue
        periods.append(period)
        if period["valid_to"] is None:
            issues.append({
                "severity": "warning", "code": "open_office_end",
                "reason": "Missing end treated as an open interval by project convention",
                "record": statement,
            })
    return periods, unselected, issues


def office_periods_overlap(first_period, second_period):
    """Compare inclusive intervals, interpreting a missing end as open"""
    first_end = first_period["valid_to"] or "9999-12-31"
    second_end = second_period["valid_to"] or "9999-12-31"
    return first_period["valid_from"] <= second_end and second_period["valid_from"] <= first_end


def check_office_overlaps(periods):
    """Flag overlapping periods for the same leader without changing them"""
    issues = []
    for period_index, first_period in enumerate(periods):
        for second_period in periods[period_index + 1:]:
            if first_period["leader_qid"] != second_period["leader_qid"]:
                continue
            if office_periods_overlap(first_period, second_period):
                issues.append({
                    "severity": "error", "code": "overlapping_office_periods",
                    "reason": "Configured office periods overlap; a unique mandate requires review",
                    "records": [first_period, second_period],
                })
    return issues


def find_visit_offices(visit, periods):
    """Validate the visit dates and find offices valid at the visit's start."""
    start_date = date.fromisoformat(visit["start_date"])
    end_date = date.fromisoformat(visit["end_date"])
    if end_date < start_date:
        raise ValueError("Visit end date precedes start date")

    matching_periods = []
    for period in periods:
        if period["leader_qid"] != visit.get("leader_qid"):
            continue
        if period["valid_from"] > start_date.isoformat():
            continue
        if period["valid_to"] is not None and period["valid_to"] < start_date.isoformat():
            continue
        matching_periods.append(period)
    return matching_periods


def resolve_visit_office(visit, periods):
    """Return one enriched visit and its optional resolution issue."""
    resolved_visit = {**visit, "office_resolution_status": "needs_review"}
    try:
        candidates = find_visit_offices(visit, periods)
    except (ValueError, TypeError, KeyError) as error:
        return resolved_visit, {
            "severity": "error", "code": "invalid_visit_dates",
            "reason": str(error), "record": visit,
        }
    if len(candidates) != 1:
        return resolved_visit, {
            "severity": "error", "code": "no_matching_office" if not candidates else "ambiguous_office",
            "reason": f"Expected one office valid at visit start, found {len(candidates)}",
            "record": visit,
        }

    period = candidates[0]
    resolved_visit.update({
        "office_resolution_status": "resolved",
        "office_statement_uri": period["statement_uri"],
        "position_qid": period["position_qid"],
        "visitor_country_iso3": period["represented_country_iso3"],
        "office_end_date_status": period["end_date_status"],
    })
    return resolved_visit, None


def resolve_visit_offices(visits, periods):
    """Resolve visits independently, retaining every row and its issues."""
    resolved_visits = []
    issues = []
    for visit in visits:
        resolved_visit, issue = resolve_visit_office(visit, periods)
        resolved_visits.append(resolved_visit)
        if issue is not None:
            issues.append(issue)
    return resolved_visits, issues
