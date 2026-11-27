# Diplomap
Template by [Riccardo Tommasini](riccardotommasini.com/) from [INSA Lyon](https://www.insa-lyon.fr/).

![Insalogo](./images/logo-insa_0.png)

Students: CESBRON Charles, HABSIEGER Carl, MASSILA AKENDENGUE Daniel, PAGET Pierre-Louis

### Abstract

DiploMap is an interactive globe and diplomatic-network explorer that shows where world leaders travelled and how media coverage and bilateral interactions shift around those visits.

## Project Objectives

The project aims to:

- analyze where leaders travel and how often;
- compare media tone before and after diplomatic visits;
- measure changes in cooperation and conflict;
- identify the bilateral events and sources associated with a visit;
- represent travel relationships as a leader-country network.

## Getting Started (macOS and Windows)

### Prerequisites

| Tool | Version | macOS | Windows |
|---|---|---|---|
| Git | any recent | `xcode-select --install` or [git-scm.com](https://git-scm.com) | [git-scm.com](https://git-scm.com) |
| Docker Desktop | recent | [docker.com](https://www.docker.com/products/docker-desktop/) | [docker.com](https://www.docker.com/products/docker-desktop/), with the WSL 2 backend |
| Node.js | 20.19+ or 22.12+ (Vite 8) | [nodejs.org](https://nodejs.org) or `brew install node` | [nodejs.org](https://nodejs.org) |
| Python | 3.12+ | [python.org](https://www.python.org) or `brew install python` | [python.org](https://www.python.org) (tick "Add python.exe to PATH") |

On macOS the commands are `python3`; on Windows they are `python` (or `py`). The Windows commands below are for
PowerShell. Shell scripts keep LF line endings on Windows thanks to `.gitattributes`.

### 1. Local stack (Docker)

Airflow, Postgres, Neo4j, the backend and Jupyter run in Docker. A plain copy of `.env.example` holds fake
development values, enough to start the stack.

macOS:

```bash
cp .env.example .env
docker compose up -d --build --wait
```

Windows (PowerShell):

```powershell
Copy-Item .env.example .env
docker compose up -d --build --wait
```

On macOS, set `JUPYTER_UID` in `.env` to the output of `id -u` so Jupyter can save notebooks in
`business_questions/`. On Windows, keep the default `1000`.

| Service | URL | Login |
|---|---|---|
| Airflow | http://localhost:8081 | `AIRFLOW_ADMIN_USERNAME` / `AIRFLOW_ADMIN_PASSWORD` of `.env` |
| Neo4j Browser | http://localhost:7474 | `neo4j` / `NEO4J_PASSWORD` of `.env` |
| Backend (FastAPI docs) | http://localhost:8000/docs | none |
| Jupyter | http://localhost:8888 | `JUPYTER_TOKEN` of `.env` |
| Frontend image | http://localhost:3000 | placeholder page for now: use the dev server below |

Stop the stack with `docker compose down` (add `-v` to also delete the volumes, data included).

### 2. Frontend (Globe and Network views)

The frontend runs on its mock responses (`frontend/src/mocks/`) unless `VITE_API_URL` is set. Keep the mocks for
now: on this branch the backend data routes still answer 501.

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173
npm test           # Vitest
npm run build      # type check and production build
```

To read the real API once it serves data:

- macOS: `VITE_API_URL=http://localhost:8000 npm run dev`
- Windows (PowerShell): `$env:VITE_API_URL="http://localhost:8000"; npm run dev`

### 3. Python tests (warehouse and backend)

Create a virtual environment at the root of the repository.

macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install duckdb psutil pyyaml pytest httpx requests -r backend/requirements.txt
python -m pytest warehouse/tests
python -m pytest backend/tests
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install duckdb psutil pyyaml pytest httpx requests -r backend/requirements.txt
python -m pytest warehouse/tests
python -m pytest backend/tests
```

If PowerShell refuses to run `Activate.ps1`, allow local scripts once with
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. The Neo4j tests are skipped unless `NEO4J_PASSWORD` is set
and Neo4j is running.

## Database Creation

[`DB/createDB.py`](DB/createDB.py) downloads the latest GDELT export, stores
new events in a local DuckDB database, and loads the CAMEO event-code and
country reference tables. It also performs a few checks and summary queries on
the imported data.

Run it from the `DB` directory, with the virtual environment above activated, so that the local reference files
are found:

```bash
cd DB
python createDB.py
```

This script helped us become familiar with the structure of GDELT,
understand how its data is represented, and begin analyzing the
available events.

## Business Questions and SQL Queries

[`examples.sql`](examples.sql) contains the SQL queries corresponding to our
five business questions:

1. Where did each leader travel, and how often?
2. How did the media tone of bilateral GDELT events change before and after
   each visit?
3. How did the cooperative or conflictual character of bilateral events
   change?
4. Which bilateral events occurred around a visit, and which source URLs are
   attached?
5. How are leaders and countries connected through travel?

## KPI Views

The KPIs are served by two DuckDB views (contracts in [`table_contracts/`](table_contracts/)):
`v_visit_event` attributes the bilateral GDELT events to the 15 days before and the 15 days after each visit, and
`v_kpi_visit` computes, per visit, the event counts, the cooperative share, the tone and the Goldstein score before
and after, with their deltas and the low-volume and overlap flags. The `kpi_visit_day` pseudocode of
`examples.sql` is the first draft of this design.

## Repository Structure

```text
backend/            FastAPI backend (API contract, OpenAPI export, tests)
business_questions/ Analysis notebook
DB/                 Exploration script and reference data (CAMEO, countries)
frontend/           React frontend: Globe and Network views (Vite, Vitest)
ingestion/          GDELT, Wikidata and Wikipedia ingestion
orchestration/      Airflow image and DAGs
sample_datasets/    Sample rows and API example responses
table_contracts/    Table and view contracts (YAML) and modelling decisions
warehouse/          Staging, quality gate, star schema, views, Neo4j projection, tests
examples.sql        Business-question queries and KPI-table pseudocode
docker-compose.yml  Local stack
images/             Project images
```
