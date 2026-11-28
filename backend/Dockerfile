# Backend image: FastAPI app serving /health, /docs, /openapi.json and the API
# routes (contract of task P1-12). The modules are copied flat into /app.
FROM python:3.12.16-slim-bookworm

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py api.py schemas.py examples.py ./

RUN useradd --uid 10001 --no-create-home app
USER app

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
