import re
from datetime import date

from .transit import is_transit

MONTHS = {
    "january": 1, "february": 2, "march": 3,
    "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}

def parse_single_date(date_text, year):
    """Parse single-day dates from English Wikipedia pages (e.g., '12 March')"""
    day_text, month_name = date_text.split()
    month_number = MONTHS.get(month_name.lower())
    if month_number is None:
        raise ValueError(f"Unknown month: {month_name}")
    return date(year, month_number, int(day_text))


def parse_date_range(date_text, year):
    """Parse '12–14 March' or '31 March–2 April' within the given year"""
    normalized_text = date_text.replace("–", "-").replace("—", "-")
    start_text, end_text = normalized_text.split("-")
    start_text = start_text.strip()
    end_text = end_text.strip()

    # In '12–14 March', both days use the month written at the end.
    if start_text.isdigit():
        month_name = end_text.split()[-1]
        start_text = f"{start_text} {month_name}"

    start_date = parse_single_date(start_text, year)
    end_date = parse_single_date(end_text, year)
    if end_date < start_date:
        raise ValueError(f"End date precedes start date: {date_text}")

    return start_date, end_date


def clean_date_text(date_text):
    """Remove Wikipedia reference markers and normalize whitespace"""
    text_without_notes = re.sub(r"\[[^\]]*\]", "", date_text)
    return " ".join(text_without_notes.split())


def parse_visit_dates(date_raw, year):
    """Return a start and end date for either a single day or a range."""
    date_text = clean_date_text(date_raw)
    if not date_text:
        raise ValueError("Visit date is empty")

    if any(separator in date_text for separator in ("-", "–", "—")):
        return parse_date_range(date_text, year)

    visit_date = parse_single_date(date_text, year)
    return visit_date, visit_date


def clean_country_name(country_raw):
    """Remove reference markers and extra spaces without splitting the name."""
    country_without_notes = re.sub(r"\[[^\]]*\]", "", country_raw)
    return " ".join(country_without_notes.split())


def normalize_visit(visit):
    """Add normalized dates and country name while preserving raw fields."""
    start_date, end_date = parse_visit_dates(visit["date_raw"], visit["year"])
    return {
        **visit,
        "host_country_name": clean_country_name(visit["host_country_raw"]),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "is_transit": is_transit(visit.get("details_raw"), visit.get("host_country_raw")),
    }
