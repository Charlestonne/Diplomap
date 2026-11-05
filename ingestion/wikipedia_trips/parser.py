from io import StringIO

import pandas as pd
from bs4 import BeautifulSoup


def get_year_tables(html, year):
    """Return Wikipedia tables inside the requested year section"""
    page_html = BeautifulSoup(html, "html.parser")

    year_tables = []
    year_heading_level = None
    inside_year = False

    # Traverse headings and tables in document order
    for element in page_html.find_all(
        ["h2", "h3", "h4", "h5", "h6", "table"]
    ):
        if element.name.startswith("h"):
            heading_level = int(element.name[1])
            heading_title = element.get_text(" ", strip=True)

            if inside_year and heading_level <= year_heading_level:
                inside_year = False

            if heading_title == str(year):
                year_heading_level = heading_level
                inside_year = True

        elif (
            inside_year
            and "wikitable" in element.get("class", [])
            # Ignore tables nested inside another table.
            and element.find_parent("table") is None
        ):
            year_tables.append(element)

    return year_tables


def parse_trip_row(linked_cells):
    """Convert (text, first_link) cells into a raw trip dictionary"""
    trip_data = {}
    for column_name, cell_content in linked_cells.items():
        trip_data[column_name] = (
            cell_content[0] if isinstance(cell_content, tuple) else ""
        )

    country_cell = linked_cells["Country"]
    trip_data["country_link"] = (
        country_cell[1] if isinstance(country_cell, tuple) else None
    )
    return trip_data


def parse_table(table):
    """Read the expected trip columns and preserve the first country link"""
    trip_dataframe = pd.read_html(StringIO(str(table)), extract_links="body")[0]
    required_columns = ["Country", "Areas visited", "Date(s)", "Details"]

    if not all(column_name in trip_dataframe.columns for column_name in required_columns):
        return []

    linked_trip_rows = trip_dataframe[required_columns].to_dict(orient="records")
    return [parse_trip_row(linked_cells) for linked_cells in linked_trip_rows]
