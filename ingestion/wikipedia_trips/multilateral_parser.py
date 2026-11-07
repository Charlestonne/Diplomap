"""Read the meeting table without matching its events to visits yet.

Entry point: extract_multilateral_meetings(), at the bottom of this file.
The HTML is already downloaded; BeautifulSoup only navigates its contents.
"""
import re

from bs4 import BeautifulSoup
from .normalizer import MONTHS, parse_visit_dates


MONTH_PATTERN = "|".join(MONTHS)
# Locate dates in cells that may also contain a location and reference notes.
# parse_visit_dates() converts the matched text into dates later.
DATE_PATTERN = re.compile(
    # Match either a single day/month or a range of days with one or two months.
    rf"\b\d{{1,2}}(?:\s+(?:{MONTH_PATTERN}))?"
    rf"\s*[-–—]\s*\d{{1,2}}\s+(?:{MONTH_PATTERN})\b"
    rf"|\b\d{{1,2}}\s+(?:{MONTH_PATTERN})\b",
    re.IGNORECASE,
)


def expand_table_cells(table):
    """Expand row/column spans, retaining the HTML cells and their styles"""
    # Key: (row, column)
    # Value: the HTML tag representing the cell
    occupied_cells = {}
    rows = [row for row in table.find_all("tr") if row.find_parent("table") is table]
    for row_index, row in enumerate(rows):
        column_index = 0
        for cell in row.find_all(["td", "th"], recursive=False): # only direct children of <tr> are considered, not nested tables
            while (row_index, column_index) in occupied_cells:
                column_index += 1
            row_span = int(cell.get("rowspan", 1))
            column_span = int(cell.get("colspan", 1))
            if row_span < 1 or column_span < 1:
                raise ValueError("Unsupported zero or negative table span")
            for row_offset in range(row_span):
                for column_offset in range(column_span):
                    # Reuse the same HTML object in every position covered by the cell
                    occupied_cells[row_index + row_offset, column_index + column_offset] = cell
            column_index += column_span
    # Convert the dictionary into a grid accessed as grid[row][column].
    # Positions without a cell become None through .get().
    width = max((column for _, column in occupied_cells), default=-1) + 1
    return [[occupied_cells.get((row, column)) for column in range(width)] for row in range(len(rows))]


def read_color(style, property_name):
    """Normalize the inline hex colors used in the page's legend"""
    match = re.search(rf"(?:^|;)\s*{property_name}\s*:\s*(#[0-9a-f]{{3,6}})\b", style, re.I)
    if not match:
        return None
    color = match[1].lower()
    if len(color) == 4:
        # The shorthand #ffb expands to #ffffbb.
        color = "#" + "".join(character * 2 for character in color[1:])
    return color


def read_attendance_colors(table):
    """Read each colored legend marker, even when labels share one HTML block"""
    legend_copy = BeautifulSoup(str(table), "html.parser") # working on a copy of the table because we will replace tags in it
    # CSS selector: every <span> with a style attribute.
    for marker in legend_copy.select("span[style]"):
        color = read_color(marker["style"], "color")
        if color:
            # Replace the colored square with a text marker that retains its color.
            marker.replace_with(f"[[legend:{color}]]")
    # fragments with spaces and strips their surrounding whitespace.
    legend_text = legend_copy.get_text(" ", strip=True)
    markers = re.findall(
        r"\[\[legend:(#[0-9a-f]{6})\]\]\s*=\s*(did not attend|future event)",
        legend_text, flags=re.IGNORECASE,
    )
    # Interpret colors using this page's legend
    return {
        color.lower(): "did_not_attend" if label.casefold() == "did not attend" else "future_event"
        for color, label in markers
    }


def meeting_cell_status(cell, attendance_colors):
    # The background may be set on <td> or on its parent <tr>.
    # A background set directly on the cell takes precedence.
    row_style = cell.find_parent("tr").get("style", "")
    style = cell.get("style", "") if "background" in cell.get("style", "").casefold() else row_style
    color = read_color(style, r"background(?:-color)?")
    if color in attendance_colors:
        return attendance_colors[color]
    if "background" in style.casefold():
        # A background color not explained by the legend cannot confirm attendance.
        return "attendance_requires_review"
    # A superscript note (<sup>) may indicate that a minister attended instead
    # of the president. Without interpreting the note, flag it for review.
    if cell.find("sup"):
        return "attendance_requires_review"
    # Table convention: an unmarked cell is assumed to indicate attendance.
    # Text indicating cancellation or remote attendance is handled below.
    return "in_person"


def read_location(cell):
    """Read the host country from its flag and the following location text"""
    # .flagicon selects elements with the CSS class flagicon.
    # The flag often carries the country name, which may not appear as visible text.
    flags = cell.select(".flagicon")
    if len(flags) != 1:
        raise ValueError("Expected exactly one host country flag in the meeting cell")
    flag = flags[0]
    country_link = flag.find("a", title=True)
    flag_image = flag.find("img", alt=True)
    country_name = country_link["title"] if country_link else (flag_image.get("alt") if flag_image else None)
    if not country_name:
        raise ValueError("Host country name is absent from the flag")
    location_parts = []
    # The country name is often followed by a comma and a city, but the city may be missing
    for sibling in flag.next_siblings:
        if getattr(sibling, "name", None) == "br":
            break
        # A sibling may be a tag (<a>Paris</a>) or a plain text node.
        location_parts.append(sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else str(sibling))
    return country_name, " ".join(" ".join(location_parts).split()).strip(" ,")


def parse_meeting_cell(cell, group, year, attendance_colors):
    """Keep every dated occurrence, including those excluded as evidence"""
    raw_text = cell.get_text(" ", strip=True)
    if raw_text.casefold() in ("", "none", "didn't exist", "did not exist"):
        return []
    date_matches = list(DATE_PATTERN.finditer(raw_text)) # returns every matched date and ist position
    if not date_matches:
        raise ValueError("No supported day/month date found in meeting cell")
    attendance = meeting_cell_status(cell, attendance_colors)
    # In "Others", an event title may appear before the first date.
    # Without a title, use the row's group: G7, NATO, EU, etc.
    event_name = raw_text[:date_matches[0].start()].strip(" ,") or group
    events = []
    for date_index, date_match in enumerate(date_matches):
        # Inspect text between this date and the next to associate "videoconference"
        # with its occurrence rather than with the entire cell.
        segment_end = date_matches[date_index + 1].start() if date_index + 1 < len(date_matches) else len(raw_text)
        date_segment = raw_text[date_match.start():segment_end].casefold()
        status = attendance
        if "cancelled" in date_segment or "canceled" in date_segment:
            status = "cancelled"
        elif "videoconference" in date_segment or "video conference" in date_segment:
            status = "remote"
        try:
            country_name, city = read_location(cell)
        except ValueError:
            if status == "in_person":
                raise
            # Retain remote or excluded meetings even if their location cannot be read;
            # they cannot be used to confirm a physical visit.
            country_name, city = None, None
        # date_match[0] is the matched text; the year comes from the selected column.
        start_date, end_date = parse_visit_dates(date_match[0], year)
        events.append({
            "group": group, "event_name": event_name,
            "host_country_name": country_name, "city": city,
            "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
            "attendance_status": status, "source_cell_text": raw_text,
        })
    return events


def extract_multilateral_meetings(page, year):
    """Return events and review items; never turn missing evidence into False."""
    # HTML --> parse tree
    soup = BeautifulSoup(page["text"], "html.parser")
    # Find the multilateral meetings section, if any. If absent, the matcher will leave is_multilateral null.
    heading = next((element for element in soup.find_all(re.compile(r"^h[2-6]$"))
                    if element.get("id") == "Multilateral_meetings"
                    or element.find(id="Multilateral_meetings") is not None
                    or element.get_text(" ", strip=True) == "Multilateral meetings"), None)
    report = {"section_status": "missing", "year": year, "events": [], "review_items": []}
    if heading is None:
        # No evidence available: the matcher will leave is_multilateral null.
        return report
    report["section_status"] = "found"
    tables = []
    # Navigate the multilateral meetings section in three steps:
    for element in heading.next_elements:
        if re.fullmatch(r"h[2-6]", element.name or "") and int(element.name[1]) <= int(heading.name[1]):
            # Stop when reaching a heading of the same or higher level than the section title (leaving the section)
            break
        if element.name == "table" and element.find_parent("table") is None:
            tables.append(element)
    found_year = False
    for table_index, table in enumerate(tables, start=1):
        grid = expand_table_cells(table)  # HTML table --> 2D list of cells, with None for empty positions
        # Find the column containing the requested year, if any
        year_header = next(((row_index, column_index) for row_index, row in enumerate(grid)
                            for column_index, cell in enumerate(row)
                            if cell is not None and cell.name == "th"
                            and cell.get_text(strip=True) == str(year)), None)
        if year_header is None:
            continue
        found_year = True
        header_index, year_column = year_header
        attendance_colors = read_attendance_colors(table)
        # Traverse the rows below the header, skipping any that are empty or already processed
        seen_cells = set()
        for row_index in range(header_index + 1, len(grid)):
            row = grid[row_index]
            group_cell, year_cell = row[0], row[year_column]
            if group_cell is None or year_cell is None or group_cell.name != "td" or id(year_cell) in seen_cells:
                continue
            seen_cells.add(id(year_cell))
            # Keep the source information for each event, so that the matcher can report any issues with the original table
            source = {
                "wiki_page_id": page["pageid"], "wiki_revision_id": page["revid"],
                "wiki_language": page.get("language", "en"),
                "source_section": "Multilateral meetings",
                "source_table_index": table_index, "source_html_row_index": row_index + 1,
            }
            try:
                # Parse the cell and add all events to the report, even those that are excluded as evidence
                events = parse_meeting_cell(year_cell, group_cell.get_text(" ", strip=True), year, attendance_colors)
                report["events"].extend({**event, **source} for event in events)
            except (ValueError, IndexError) as error:
                # an unrecognized cell, we don't know if the leader attended or not, so we keep it in the report for review
                # Not transformed into a False value but a null
                report["review_items"].append({
                    **source, "source_cell_text": year_cell.get_text(" ", strip=True),
                    "reason": str(error),
                })
    if not found_year:
        report["section_status"] = "year_not_found"
    return report
