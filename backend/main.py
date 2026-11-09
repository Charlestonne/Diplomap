# FastAPI app of the DiploMap backend. /health answers the container healthcheck;
# the API routes (contract of task P1-12, handlers not implemented yet) live in api.py.
from typing import Any

from api import add_examples, router
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="DiploMap API",
    version="0.1.0",
    description="Read-only API of the Globe and Network views. Contract only: the data routes answer 501.",
)
app.include_router(router)


@app.get("/health", operation_id="health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


def openapi() -> dict[str, Any]:
    """OpenAPI document with the example responses of api.py (nulls kept)."""
    if app.openapi_schema is None:
        schema = get_openapi(
            title=app.title, version=app.version, description=app.description, routes=app.routes
        )
        app.openapi_schema = add_examples(schema)
    return app.openapi_schema


app.openapi = openapi
