"""Classify visits that are explicitly described as transit or a stopover"""

from __future__ import annotations

import re
import unicodedata


# Keep this vocabulary deliberately narrow.  It is a flag for analysis, not a
# general-purpose interpretation of every travel description.
TRANSIT_PATTERN = re.compile(
    r"\b(?:transit(?:ed|s|ing)?|pass(?:ed)?\s+through|"
    r"refuel(?:ed|ing)?|refuelling|technical\s+stop|"
    r"stopover|layover|stop(?:ped)?\s+over)\b",
    re.IGNORECASE,
)
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


def _clean_text(value: str) -> str:
    """Normalize Unicode and whitespace for matching, without changing stored text"""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"\[[^\]]*\]", "", normalized)
    return " ".join(normalized.split())


def _contains_host_country(sentence: str, host_country: str) -> bool:
    """Return whether a sentence names the host country as a complete phrase"""
    country = _clean_text(host_country)
    if not country:
        return False
    return re.search(r"(?<!\w)" + re.escape(country) + r"(?!\w)", sentence, re.IGNORECASE) is not None


def is_transit(details_raw: str | None, host_country_raw: str | None) -> bool | None:
    """Classify transit conservatively using details and the host-country guard.
    Empty details remain unknown (``None``).
    For non-empty details, a transit expression must either start the cell
    or occur in a sentence that names the host country.
    This prevents a refuelling mention for a different country from changing the visit classification.
    """
    if details_raw is None or not str(details_raw).strip():
        return None

    details = _clean_text(str(details_raw))
    host_country = _clean_text(str(host_country_raw or ""))
    for sentence in SENTENCE_BREAK.split(details):
        expression = TRANSIT_PATTERN.search(sentence)
        if expression is None:
            continue
        starts_with_expression = expression.start() == 0
        if starts_with_expression or _contains_host_country(sentence, host_country):
            return True
    return False
