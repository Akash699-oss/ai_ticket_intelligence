# AI Customer Support Ticket Intelligence System

End-to-end AI Engineer assessment solution for the supplied `support_tickets.csv` dataset. The application ingests and validates the real CSV, persists it to local SQLite, uses an LLM to interpret natural-language questions into a strict JSON query plan, validates that plan against an allow-list, executes calculations deterministically in Pandas, detects anomalies, and exposes both a FastAPI REST API and a Streamlit UI.

## 1. Problem statement

Build a zero-cost, locally runnable support-ticket intelligence system that can:

- ingest the supplied CSV and make it queryable;
- answer natural-language questions about ticket data;
- use an LLM for natural-language understanding;
- detect abnormal resolution times and stale unresolved urgent tickets;
- expose the functionality via REST API and a minimal UI;
- be easy for an evaluator to run, inspect, and discuss in an architecture walkthrough.

This repository uses the supplied `data/support_tickets.csv` unchanged as the source dataset. No query answer is hard-coded.

## 2. Features

- CSV schema/type/value validation
- Local SQLite persistence for a queryable data store
- Ollama as the default free local LLM (`llama3.2:3b`)
- Optional Groq free-tier provider through environment variables
- Strict Pydantic JSON `QueryPlan`
- Allow-listed fields, operators, metrics, grouping dimensions, and operations
- No LLM-generated SQL, `eval`, `exec`, or arbitrary code execution
- Deterministic Pandas query execution
- Operations: `count`, `list`, `average`, `group_count`, `group_average`, `max_group_count`, `min_group_average`, `anomalies`
- Relative windows: latest dataset week / latest dataset month
- Resolution-SLA semantic predicate for questions such as “not resolved within 12 hours”
- IQR-based resolution-time anomaly detection
- Stale High/Critical unresolved-ticket detection
- FastAPI endpoints with Swagger/OpenAPI
- Streamlit dashboard
- Pytest coverage for ingestion, validation, deterministic queries, anomalies, API health/query/error handling
- One-command startup: `python run.py`

## 3. Architecture

```text
User question
    |
    v
Streamlit UI / POST /query
    |
    v
LLM Planner (Ollama default; optional Groq)
    |
    | strict JSON only
    v
Pydantic QueryPlan validation + allow-lists
    |
    v
Deterministic QueryEngine (Pandas)
    |
    +----> TicketRepository ----> supplied CSV ----> local SQLite
    |
    v
Structured result + answer + rows + metadata

GET /anomalies
    |
    v
Deterministic AnomalyDetector
    +---- IQR resolution-time rule
    +---- stale High/Critical unresolved >24h rule
```

The central safety decision is that the LLM is an **interpreter, not an executor**. It never receives permission to run SQL/Python. Its JSON output must validate against an explicit schema before deterministic code touches the data.

## 4. Project structure

```text
ai_ticket_intelligence/
├── app/
│   ├── __init__.py
│   ├── anomalies.py
│   ├── config.py
│   ├── db.py
│   ├── llm.py
│   ├── main.py
│   ├── query_engine.py
│   └── schemas.py
├── data/
│   └── support_tickets.csv
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   └── test_engine.py
├── ui.py
├── run.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── DESIGN_NOTES.md
```

A generated `data/tickets.db` appears at runtime and is intentionally ignored by Git.

## 5. Technology stack

- Python 3.11+ recommended
- FastAPI + Uvicorn
- Pandas
- SQLite (Python standard library)
- Pydantic v2
- Ollama local HTTP API
- Requests
- Streamlit
- Pytest + FastAPI TestClient / HTTPX

## 6. LLM choice and reasoning

### Default: Ollama + `llama3.2:3b`

Ollama satisfies the assessment’s zero-cost local-runtime requirement. A small model keeps local hardware requirements reasonable. The prompt asks for JSON only, and the returned payload is validated by Pydantic.

The LLM is used only to map free-form language to a safe semantic plan. Deterministic code performs filtering, grouping, counting, averaging, SLA evaluation, and anomaly calculations.

### Optional: Groq free tier

Set `LLM_PROVIDER=groq` plus `GROQ_API_KEY`. No Groq dependency is required because the project calls its OpenAI-compatible HTTPS endpoint through `requests`.

### Resilience fallback

By default, `ALLOW_RULE_FALLBACK=true`. If Ollama is unavailable, a narrow deterministic rule planner supports common assessment questions so the demo remains usable. API metadata reports `planner_backend` and any `llm_error`, so fallback use is never hidden.

For strict LLM-only evaluation:

```bash
ALLOW_RULE_FALLBACK=false python run.py
```

## 7. Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## 8. Ollama setup

1. Install Ollama from the official Ollama distribution for your OS.
2. Pull the default model:

```bash
ollama pull llama3.2:3b
```

3. Ensure Ollama is running locally. The default endpoint is:

```text
http://127.0.0.1:11434
```

You can select another local model by setting `OLLAMA_MODEL`.

## 9. Environment variables

Copy the template if you want to customize defaults:

```bash
cp .env.example .env
```

The application reads environment variables directly; `.env` is intentionally ignored by Git. If you use a `.env` file, load it in your shell or IDE before starting the app.

Important variables:

```text
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
ALLOW_RULE_FALLBACK=true
API_HOST=127.0.0.1
API_PORT=8000
UI_PORT=8501
```

Optional Groq:

```text
LLM_PROVIDER=groq
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
```

## 10. Run the complete system

From the repository root:

```bash
python run.py
```

This starts both services:

- FastAPI: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Streamlit: `http://127.0.0.1:8501`

Press `Ctrl+C` to stop both processes.

### Run services separately during development

Backend:

```bash
python -m uvicorn app.main:app --reload
```

UI:

```bash
python -m streamlit run ui.py
```

## 11. REST API

### `GET /health`

Confirms the CSV/database are ready and reports row count, columns, historical reference time, and configured planner provider.

### `POST /query`

Request:

```json
{
  "question": "How many critical tickets are unresolved?"
}
```

Response includes:

- original question;
- validated interpreted query plan;
- concise answer;
- result rows when relevant;
- metadata such as matched rows and planner backend.

### `GET /anomalies`

Returns anomaly counts, thresholds/rules, reference time, and detail rows.

Optional query parameter:

```text
relative_window=latest_week
relative_window=latest_month
```

## 12. Query-plan schema

Representative plan:

```json
{
  "operation": "count",
  "filters": [
    {"field": "status", "operator": "eq", "value": "Open"}
  ],
  "metric": null,
  "group_by": null,
  "limit": 50,
  "relative_window": null,
  "unresolved_or_over_resolution_hours": null
}
```

Allowed fields are exactly the supplied dataset columns. Result limits are bounded to 200 rows.

## 13. UI usage

The Streamlit UI provides:

- backend/API readiness indicator;
- natural-language question input;
- Run Query button;
- answer card;
- result table;
- interpreted safe plan viewer;
- metadata viewer;
- anomaly window selector;
- anomaly count metrics;
- separate ticket tables for both anomaly classes;
- rule/threshold details.

## 14. Sample questions

- How many tickets are currently open?
- How many critical tickets are unresolved?
- Which agent resolved the most tickets?
- Which agent resolved the most tickets this month?
- Which agent has the lowest average customer rating?
- What is the average customer rating for Technical category tickets?
- Show me all Critical tickets not resolved within 12 hours.
- Are there any anomalies in resolution times this week?

## 15. Example outputs from the actual supplied CSV

These values were calculated from `data/support_tickets.csv`, not invented:

| Question / calculation | Actual output |
|---|---:|
| Tickets currently `Open` | **111** |
| Critical tickets with `status != Resolved` | **31** |
| Agent(s) with most resolved tickets, all data | **AGT-09 and AGT-12 — 37 each** |
| Agent with lowest average customer rating | **AGT-08 — 3.4800** |
| Average customer rating for Technical tickets | **3.7404** |
| Critical tickets unresolved or resolved after 12h | **34** |
| Agent with most resolved tickets in latest dataset month (March 2024) | **AGT-01 — 16** |
| IQR long-resolution upper fence | **48.15 hours** |
| Resolution-time outliers above upper fence | **21** |
| Stale unresolved High/Critical tickets older than 24h | **80** |

The supplied dataset contains **500 rows**. Its `created_at` range is **2024-01-01 08:54** through **2024-03-30 18:06**. There are **173** unresolved rows with null `resolution_time_hrs` and `customer_rating`, consistent with the dataset semantics.

## 16. Anomaly detection methodology

### A. Abnormally long resolution time

Use all non-null `resolution_time_hrs` values:

```text
Q1 = 6.15
Q3 = 22.95
IQR = 16.80
Upper Fence = Q3 + 1.5 * IQR = 48.15 hours
```

A ticket is flagged when:

```text
resolution_time_hrs > 48.15
```

The supplied CSV contains **21** such tickets.

### B. Unresolved High/Critical ticket older than 24 hours

A ticket is flagged when:

```text
status != Resolved
AND priority IN (High, Critical)
AND age > 24 hours
```

Because this is a static historical dataset, age uses `max(created_at)` — **2024-03-30T18:06:00** — as the snapshot/reference time. This keeps results reproducible instead of changing every day. The supplied CSV contains **80** tickets matching this rule.

For a live production feed, replace the snapshot reference with an injected current clock or source-system snapshot timestamp.

## 17. Testing

Run:

```bash
python -m pytest -q
```

Tests cover:

- CSV ingestion and datetime conversion;
- required-column validation;
- count query;
- filters;
- averages;
- grouped/max/min grouped calculations;
- both anomaly rules and IQR threshold;
- query-plan allow-list rejection;
- `/health`;
- `/query` with a mockable deterministic planner;
- `/anomalies`;
- invalid request handling.

The deterministic query engine and API tests do not require a live LLM.

## 18. Known limitations

- The fallback planner intentionally supports only common assessment phrasing; the LLM planner provides the broader natural-language coverage.
- Query plans use a fixed set of safe analytics operations instead of arbitrary joins/formulas.
- Relative “week/month” expressions are anchored to the historical dataset reference time, not the machine clock.
- The application is single-node and loads 500 rows into memory for deterministic Pandas execution. For millions of rows, plans should compile to parameterized SQL over an analytics database.
- Authentication/rate limiting are outside the scope of this local assessment prototype.
- The UI assumes the FastAPI backend is reachable at `API_URL`.

## 19. Future improvements

- JSON-schema-constrained generation where supported by the selected local model
- More semantic predicates (percentiles, medians, trend comparisons, multiple OR groups)
- Parameterized SQL compiler for larger datasets
- Response caching and request tracing
- Authentication and rate limiting
- Docker Compose for identical evaluator environments
- CI workflow for pytest/lint/type checks
- LLM evaluation set with paraphrase/adversarial-plan tests
- Natural-language explanation layer that summarizes deterministic result rows without altering calculations

## 20. Deployment / submission readiness

The official assessment submission is a GitHub repository and requires zero-cost local execution. The primary deployment path is therefore evaluator-local rather than a paid/public cloud service.

Before submission:

```bash
python scripts/preflight.py
python -m pytest -q
python run.py
```

With the app running, a second terminal can perform an end-to-end smoke test:

```bash
python scripts/smoke_test.py
```

For remote IDEs or forwarded-port environments, bind both servers externally while keeping the UI-to-API connection local:

```bash
API_HOST=0.0.0.0 UI_HOST=0.0.0.0 python run.py
```

See `DEPLOYMENT.md` for the full evaluator deployment and GitHub submission checklist.

## 21. Assessment requirement mapping

| Assessment requirement | Implementation |
|---|---|
| Ingest CSV / make queryable | `TicketRepository` validates supplied CSV and persists SQLite |
| Natural-language questions | Ollama/Groq `Planner` -> strict `QueryPlan` |
| LLM required | Ollama default, configurable local model |
| No arbitrary SQL from LLM | No SQL generation path exists; allow-listed plan only |
| Deterministic calculations | `QueryEngine` using Pandas |
| Abnormally long resolution anomalies | `AnomalyDetector`, IQR upper fence |
| Unresolved urgent >24h | deterministic snapshot-age rule |
| REST API | FastAPI `/health`, `/query`, `/anomalies` |
| Minimal UI | Streamlit `ui.py` |
| Error handling | Pydantic/FastAPI validation + data validation + planner fallback/error metadata |
| Zero-cost local run | Ollama + local SQLite/Pandas |
| One-command startup | `python run.py` |
| README/setup/examples/limitations | this file |
| requirements file | `requirements.txt` |
| Tests | `tests/` |

## 22. Design assumptions

The official brief is slightly inconsistent in one place by saying “REST API ... OR a minimal UI” while the problem statement says both are required. This project implements **both** to satisfy the stricter requirement.

See `DESIGN_NOTES.md` for architectural trade-offs and historical-time semantics.
