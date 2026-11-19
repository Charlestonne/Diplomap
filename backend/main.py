# PLACEHOLDER, replace in its own ticket
# Minimal FastAPI app so the backend container starts and answers its healthcheck.
from fastapi import FastAPI

app = FastAPI(title="DiploMap backend (placeholder)")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
