from datetime import datetime, timezone

from .qid_cache import DEFAULT_QID_CACHE, load_qid_cache, save_qid_cache
from .scraper import fetch_page_qids


def resolve_page_qids(page_titles, language="en", cache_path=DEFAULT_QID_CACHE, refresh=False):
    """Return QIDs and statuses for titles, from cache or MediaWiki."""
    qid_cache = load_qid_cache(cache_path)
    if language not in qid_cache:
        qid_cache[language] = {}
    cached_titles = qid_cache[language]

    # Each title is processed only once, even if it appears in multiple visits
    unique_titles = list(dict.fromkeys(page_titles))
    titles_to_fetch = []
    for page_title in unique_titles:
        if refresh or page_title not in cached_titles:
            titles_to_fetch.append(page_title)

    # Known results remain usable locally, even if the MediaWiki API is temporarily unavailable
    if titles_to_fetch:
        fetched_qids = fetch_page_qids(titles_to_fetch, language)
        resolved_at = datetime.now(timezone.utc).isoformat()
        for page_title, resolution in fetched_qids.items():
            cached_titles[page_title] = {
                **resolution,
                "resolved_at": resolved_at,
            }
        save_qid_cache(qid_cache, cache_path)

    requested_resolutions = {}
    for page_title in unique_titles:
        requested_resolutions[page_title] = cached_titles[page_title]
    return requested_resolutions


def resolve_host_country_qids(visits, cache_path=DEFAULT_QID_CACHE, refresh=False):
    """ Add the host country QID and its status without dropping any visit """
    country_names_by_language = {}
    for visit in visits:
        country_name = visit["host_country_name"]
        if not country_name:
            continue
        language = visit["wiki_language"]
        if language not in country_names_by_language:
            country_names_by_language[language] = set()
        country_names_by_language[language].add(country_name)

    # A country is resolved on its own language wiki
    country_resolutions_by_language = {}
    for language, country_names in country_names_by_language.items():
        country_resolutions_by_language[language] = resolve_page_qids(
            sorted(country_names), language, cache_path, refresh
        )

    enriched_visits = []
    for visit in visits:
        country_name = visit["host_country_name"]
        language = visit["wiki_language"]
        if country_name:
            country_resolution = country_resolutions_by_language[language][country_name]
        else:
            # An empty cell is preserved, but does not trigger any lookup.
            country_resolution = {
                "qid": None,
                "resolved_title": None,
                "status": "empty_name",
            }

        enriched_visit = dict(visit)
        enriched_visit["host_country_qid"] = country_resolution["qid"]
        enriched_visit["host_country_qid_status"] = country_resolution["status"]
        enriched_visit["host_country_wikipedia_title"] = country_resolution["resolved_title"]
        enriched_visits.append(enriched_visit)
    return enriched_visits


def resolve_leader_qid(visits, leader, cache_path=DEFAULT_QID_CACHE, refresh=False):
    """Resolve the inventory's leader page once and enrich every retained visit."""
    if not visits:
        return []

    leader_page = leader["leader_page"]
    language = leader["leader_language"]
    page_resolutions = resolve_page_qids([leader_page], language, cache_path, refresh)
    leader_resolution = page_resolutions[leader_page]

    enriched_visits = []
    for visit in visits:
        enriched_visit = dict(visit)
        # Keep the inventory identifier separate from the Wikidata identifier.
        enriched_visit["leader_local_id"] = leader["leader_id"]
        enriched_visit["leader_qid"] = leader_resolution["qid"]
        enriched_visit["leader_qid_status"] = leader_resolution["status"]
        enriched_visit["leader_wikipedia_title"] = leader_resolution["resolved_title"]
        enriched_visits.append(enriched_visit)
    return enriched_visits
