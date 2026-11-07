import re
import unicodedata

from .multilateral_parser import extract_multilateral_meetings


def comparable_text(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def meeting_matches_visit(event, visit):
    """Require capture, host country, overlapping dates and a matching location"""
    if (event["wiki_page_id"], event["wiki_revision_id"], event["wiki_language"]) != (
        visit["wiki_page_id"], visit["wiki_revision_id"], visit["wiki_language"]):
        return False
    if comparable_text(event["host_country_name"]) != comparable_text(visit["host_country_name"]):
        return False
    if event["end_date"] < visit["start_date"] or event["start_date"] > visit["end_date"]:
        return False
    city = comparable_text(event["city"])
    visited_places = comparable_text(visit["areas_visited_raw"])
    return bool(city and re.search(r"(?<!\w)" + re.escape(city) + r"(?!\w)", visited_places))


def annotate_multilateral_visits(visits, page, year):
    """Confirm positive evidence only and preserve all visits and original fields."""
    report = extract_multilateral_meetings(page, year)
    annotated_visits = []
    for visit in visits:
        matching_events = [
            event for event in report["events"]
            if event["attendance_status"] == "in_person" and meeting_matches_visit(event, visit)
        ]
        # One meeting matching several visit rows is not assigned automatically
        confirmed_events = []
        for event in matching_events:
            matching_rows = [candidate for candidate in visits if meeting_matches_visit(event, candidate)]
            if len(matching_rows) == 1:
                confirmed_events.append(event)
            else:
                review = {"reason": "Meeting overlaps several visit rows", "event": event}
                if review not in report["review_items"]:
                    report["review_items"].append(review)
        annotated_visit = {
            **visit,
            "is_multilateral": True if confirmed_events else None,
            "multilateral_status": "confirmed" if confirmed_events else "unconfirmed",
            "multilateral_evidence": confirmed_events,
        }
        annotated_visits.append(annotated_visit)
    return annotated_visits, report
