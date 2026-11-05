from datetime import date

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
