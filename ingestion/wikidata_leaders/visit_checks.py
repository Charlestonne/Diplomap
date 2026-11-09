from collections import Counter
from datetime import date

from .office_resolution import check_office_overlaps

def visit_identity(visit):
    """Compare visits within the supplied collection, independently of revision."""
    return tuple(visit.get(field) for field in (
        "leader_qid", "host_country_qid", "start_date", "end_date", "areas_visited_raw",
    ))


def finalize_visit_resolution(visits, periods):
    """Record row blockers, inclusive duration and a combined resolution status."""
    counts = Counter(visit_identity(visit) for visit in visits)
    overlapping_leaders = set()
    for issue in check_office_overlaps(periods):
        overlapping_leaders.update(period["leader_qid"] for period in issue["records"])
    results = []
    issues = []
    for visit in visits:
        resolved = dict(visit)
        blockers = []
        if visit.get("office_resolution_status") != "resolved":
            blockers.append("unresolved_office")
        if visit.get("country_resolution_status") != "resolved":
            blockers.append("unresolved_countries")
        if visit.get("leader_qid") in overlapping_leaders:
            blockers.append("overlapping_office_periods")
        if visit.get("host_country_qid") == visit.get("visitor_country_qid") and visit.get("host_country_qid"):
            blockers.append("same_visitor_and_host")
        if counts[visit_identity(visit)] > 1:
            blockers.append("duplicate_visit")
        if not visit.get("wiki_page_id") or not visit.get("wiki_revision_id"):
            blockers.append("missing_wikipedia_provenance")
        try:
            duration = (date.fromisoformat(visit["end_date"]) - date.fromisoformat(visit["start_date"])).days + 1
            if duration < 1:
                raise ValueError("Reversed visit dates")
            resolved["duration_days"] = duration
        except (KeyError, TypeError, ValueError):
            blockers.append("invalid_visit_dates")
        resolved["resolution_status"] = "needs_review" if blockers else "resolved"
        resolved["resolution_blockers"] = blockers
        results.append(resolved)
        if blockers:
            issues.append({"severity": "error", "code": "visit_resolution_blocked",
                           "reasons": blockers, "record": visit})
    return results, issues
