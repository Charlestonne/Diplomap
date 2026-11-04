
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO


def get_year_tables(html, year):
    """Return Wikipedia tables inside the requested year section."""
    soup = BeautifulSoup(html, "html.parser")

    tables = []
    year_heading_level = None
    inside_year = False

    # Traverse headings and tables in document order
    for element in soup.find_all(
        ["h2", "h3", "h4", "h5", "h6", "table"]
    ):
        if element.name.startswith("h"):
            level = int(element.name[1])
            title = element.get_text(" ", strip=True)

            if inside_year and level <= year_heading_level:
                inside_year = False

            if title == str(year):
                year_heading_level = level
                inside_year = True

        elif (
            inside_year
            and "wikitable" in element.get("class", [])
            # Ignore tables nested inside another table.
            and element.find_parent("table") is None
        ):
            tables.append(element)

    return tables


def parse_table(table):
    """Return trip rows"""
    df = pd.read_html(StringIO(str(table)))[0]

    required_columns = [
        "Country",
        "Areas visited",
        "Date(s)",
        "Details"
    ]

    if not all(col in df.columns for col in required_columns):
        return []

    return df[required_columns].fillna("").to_dict(orient="records")
