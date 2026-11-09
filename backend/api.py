"""Routes of the DiploMap API (task P1-12): the contract only.

Every handler answers HTTP 501 "not implemented": there is no database access
yet. The routes carry their response model, a summary and an example response
(backend/examples.py), so that the OpenAPI document (/docs, backend/openapi.json)
can be reviewed by P4 before the serving queries are written.

Flat imports: in the container the backend files sit side by side in /app
(uvicorn main:app); the tests put backend/ on sys.path.
"""

from __future__ import annotations

from typing import Annotated, Any

from examples import EXAMPLES
from fastapi import APIRouter, HTTPException, Path, Query
from schemas import (
    ErrorResponse,
    Leader,
    Network,
    VisitDetail,
    VisitEvent,
    VisitKpis,
    VisitSummary,
)

router = APIRouter()

NOT_IMPLEMENTED = "not implemented"

VisitKey = Annotated[int, Path(ge=1, description="Public identifier of the visit.")]


# operation id -> example name in examples.EXAMPLES (shown as the 200 example in /docs).
ROUTE_EXAMPLES = {
    "list_leaders": "leaders",
    "list_visits": "visits",
    "get_visit": "visit",
    "get_visit_kpis": "visit_kpis",
    "get_visit_events": "visit_events",
    "get_network": "network",
}


def _responses(*, not_found: bool = False) -> dict[int | str, dict[str, Any]]:
    """OpenAPI error responses of a route: the 501 of the stub and, for one visit, the 404."""
    responses: dict[int | str, dict[str, Any]] = {
        501: {"model": ErrorResponse, "description": "Not implemented yet (contract only)."},
    }
    if not_found:
        responses[404] = {"model": ErrorResponse, "description": "No visit with this visit_key."}
    return responses


def add_examples(openapi_schema: dict[str, Any]) -> dict[str, Any]:
    """Put the 200 example of each route into a generated OpenAPI document.

    Done after generation on purpose: FastAPI drops null values from examples
    declared on the route, which would hide the nullable fields (valid_to,
    source_url, the deltas) from the example responses.
    """
    for item in openapi_schema["paths"].values():
        for operation in item.values():
            name = ROUTE_EXAMPLES.get(operation.get("operationId"))
            if name is not None:
                content = operation["responses"]["200"]["content"]["application/json"]
                content["example"] = EXAMPLES[name]
    return openapi_schema


def _not_implemented() -> HTTPException:
    return HTTPException(status_code=501, detail=NOT_IMPLEMENTED)


@router.get(
    "/leaders",
    response_model=list[Leader],
    operation_id="list_leaders",
    summary="List the leaders and their offices",
    tags=["leaders"],
    responses=_responses(),
)
def list_leaders() -> list[Leader]:
    """Leaders of dim_leader, one item per leader_id, with their offices (SCD Type 2 versions)."""
    raise _not_implemented()


@router.get(
    "/visits",
    response_model=list[VisitSummary],
    operation_id="list_visits",
    summary="List the visits",
    tags=["visits"],
    responses=_responses(),
)
def list_visits(
    leader_id: Annotated[
        str | None, Query(pattern=r"^Q[0-9]+$", description="Only the visits of this leader (Wikidata QID).")
    ] = None,
) -> list[VisitSummary]:
    """Visits of fact_visit (Globe view), ordered by start date, optionally for one leader."""
    raise _not_implemented()


@router.get(
    "/visits/{visit_key}",
    response_model=VisitDetail,
    operation_id="get_visit",
    summary="Get one visit",
    tags=["visits"],
    responses=_responses(not_found=True),
)
def get_visit(visit_key: VisitKey) -> VisitDetail:
    """One visit with the office of its leader, its PRE and POST windows and its lineage."""
    raise _not_implemented()


@router.get(
    "/visits/{visit_key}/kpis",
    response_model=VisitKpis,
    operation_id="get_visit_kpis",
    summary="Get the PRE vs POST indicators of one visit",
    tags=["visits"],
    responses=_responses(not_found=True),
)
def get_visit_kpis(visit_key: VisitKey) -> VisitKpis:
    """One row of v_kpi_visit. Null means and deltas when a window has no event; counts always present."""
    raise _not_implemented()


@router.get(
    "/visits/{visit_key}/events",
    response_model=list[VisitEvent],
    operation_id="get_visit_events",
    summary="List the GDELT events attributed to one visit",
    tags=["visits"],
    responses=_responses(not_found=True),
)
def get_visit_events(visit_key: VisitKey) -> list[VisitEvent]:
    """Rows of v_visit_event for the visit, ordered by event date: events of the PRE and POST windows."""
    raise _not_implemented()


@router.get(
    "/network",
    response_model=Network,
    operation_id="get_network",
    summary="Get the leader-country network",
    tags=["network"],
    responses=_responses(),
)
def get_network() -> Network:
    """Leader VISITED and REPRESENTS Country graph (Neo4j projection), shared destinations, reciprocal visits."""
    raise _not_implemented()
