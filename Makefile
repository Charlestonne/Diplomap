SHELL := /bin/sh

COMPOSE := docker compose
AIRFLOW_EXEC := $(COMPOSE) exec -T airflow-scheduler airflow
GDELT_START_DATE ?= 2024-12-17

.PHONY: help up down status health dags errors compile test enable trigger-wikipedia trigger-gdelt pipeline

help:
	@printf '%s\n' \
		'make up                  Start the Docker stack' \
		'make status              Show container status' \
		'make health              Check Airflow health' \
		'make dags                List Airflow DAGs' \
		'make errors              Show DAG import errors' \
		'make compile             Check Python syntax' \
		'make test                Run the Python test suite' \
		'make enable              Unpause all project DAGs' \
		'make trigger-wikipedia   Trigger the Wikipedia DAG' \
		'make trigger-gdelt       Trigger the GDELT DAG' \
		'make pipeline             Start the stack and trigger ingestion'

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

status:
	$(COMPOSE) ps

health:
	curl --fail --silent --show-error http://localhost:8081/api/v2/monitor/health
	@printf '\n'

dags:
	$(AIRFLOW_EXEC) dags list

errors:
	$(AIRFLOW_EXEC) dags list-import-errors

compile:
	python3 -m py_compile ingestion/wikipedia_trips/*.py ingestion/wikidata_leaders/*.py orchestration/dags/*.py

test:
	python3 -m pytest

enable:
	$(AIRFLOW_EXEC) dags unpause diplomap_ingest_wikipedia
	$(AIRFLOW_EXEC) dags unpause diplomap_ingest_wikidata
	$(AIRFLOW_EXEC) dags unpause diplomap_ingest_gdelt
	$(AIRFLOW_EXEC) dags unpause diplomap_build_warehouse

trigger-wikipedia:
	$(AIRFLOW_EXEC) dags unpause diplomap_ingest_wikipedia
	$(AIRFLOW_EXEC) dags trigger diplomap_ingest_wikipedia

trigger-gdelt:
	$(AIRFLOW_EXEC) dags unpause diplomap_ingest_gdelt
	$(AIRFLOW_EXEC) dags trigger diplomap_ingest_gdelt --conf '{"start_date":"$(GDELT_START_DATE)"}'

pipeline: up
	@echo 'Waiting for the Airflow API...'
	@until curl --fail --silent http://localhost:8081/api/v2/monitor/health >/dev/null; do sleep 2; done
	$(MAKE) enable
	$(MAKE) trigger-wikipedia
	$(MAKE) trigger-gdelt
	@echo 'Wikipedia and GDELT triggered; asset dependencies will trigger Wikidata and the warehouse.'
