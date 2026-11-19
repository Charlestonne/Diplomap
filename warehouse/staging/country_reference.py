"""Load and join the shared ISO and CAMEO country references."""

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from warehouse.duckdb_client import DEFAULT_DATABASE, open_database


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAMEO_FILE = PROJECT_ROOT / "DB/CAMEO.country.txt"
DEFAULT_ISO_FILE = PROJECT_ROOT / "DB/ISO.country.csv"
EXCLUDED_CAMEO_CODES = {
    "WSB", "BAG", "GZS", "AFR", "ASA", "BLK", "CRB", "CAU", "CFR", "CAS",
    "CEU", "EIN", "EAF", "EEU", "EUR", "LAM", "MEA", "MDT", "NAF", "NMR",
    "PGS", "SCN", "SAM", "SAS", "SEA", "SAF", "WAF", "WST", "ANT",
}
CAMEO_ISO_ALIASES = {"TMP": "TLS", "IMY": "IMN", "MTN": "MNE", "ROM": "ROU"}


def load_country_reference(
    connection,
    cameo_file=DEFAULT_CAMEO_FILE,
    iso_file=DEFAULT_ISO_FILE,
):
    """Replace the shared reference table and its staging join view."""
    reference = build_country_reference(cameo_file, iso_file)
    connection.register("country_reference_input", reference)
    connection.execute(
        """
        CREATE OR REPLACE TABLE stg_country_reference AS
        SELECT iso3_code, country_name, cameo_code, region,
               source_cameo_file, source_iso_file, loaded_at
        FROM country_reference_input
        """
    )
    connection.execute(
        """
        CREATE OR REPLACE VIEW stg_country_enriched AS
        SELECT country.collection_id,
               country.country_qid,
               country.country_name AS collected_country_name,
               country.iso3_code,
               country.fips_code,
               reference.country_name AS reference_country_name,
               reference.cameo_code,
               reference.region,
               country.source_file,
               country.source_record,
               country.loaded_at
        FROM stg_country AS country
        LEFT JOIN stg_country_reference AS reference
          ON reference.iso3_code = country.iso3_code
        """
    )
    connection.unregister("country_reference_input")
    return {"reference_rows": len(reference), "source_rows": len(reference)}


def build_country_reference(cameo_file, iso_file):
    cameo = pd.read_csv(cameo_file, sep="\t", dtype=str)
    iso = pd.read_csv(iso_file, dtype=str)
    required_cameo_columns = {"CODE", "LABEL"}
    required_iso_columns = {"alpha-3", "name", "region"}
    if not required_cameo_columns.issubset(cameo.columns):
        raise ValueError("CAMEO country reference is missing CODE or LABEL")
    if not required_iso_columns.issubset(iso.columns):
        raise ValueError("ISO country reference is missing alpha-3, name or region")

    cameo = cameo.loc[~cameo["CODE"].isin(EXCLUDED_CAMEO_CODES)].copy()
    cameo["iso3_code"] = cameo["CODE"].replace(CAMEO_ISO_ALIASES)
    reference = cameo.merge(
        iso[["alpha-3", "name", "region"]],
        left_on="iso3_code",
        right_on="alpha-3",
        how="inner",
        validate="one_to_one",
    )
    reference = reference.rename(columns={"CODE": "cameo_code", "name": "country_name"})
    reference = reference[["iso3_code", "country_name", "cameo_code", "region"]].copy()
    if reference["iso3_code"].duplicated().any():
        raise ValueError("Country reference contains duplicate ISO3 codes")
    reference["source_cameo_file"] = str(Path(cameo_file).resolve())
    reference["source_iso_file"] = str(Path(iso_file).resolve())
    reference["loaded_at"] = datetime.now(timezone.utc)
    return reference


def main():
    parser = argparse.ArgumentParser(description="Load the ISO/CAMEO country reference into DuckDB")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--cameo-file", default=DEFAULT_CAMEO_FILE)
    parser.add_argument("--iso-file", default=DEFAULT_ISO_FILE)
    arguments = parser.parse_args()
    with open_database(arguments.database) as connection:
        connection.execute("BEGIN TRANSACTION")
        try:
            summary = load_country_reference(connection, arguments.cameo_file, arguments.iso_file)
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
    print(summary)


if __name__ == "__main__":
    main()
