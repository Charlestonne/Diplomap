from datetime import date

MONTHS = {
    "january": 1, "february": 2, "march": 3,
    "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}

def parse_single_date(date_text, year):
    """Parse single-day dates from English Wikipedia pages"""
    day_text, month_name = date_text.split()
    month_number = MONTHS.get(month_name.lower())
    if month_number is None:
        raise ValueError(f"Unknown month: {month_name}")
    return date(year, month_number, int(day_text))
