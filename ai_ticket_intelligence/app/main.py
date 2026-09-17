from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException

from .config import settings
from .db import TicketRepository, DataValidationError
from .query_engine import QueryEngine, QueryExecutionError
from .anomalies import AnomalyDetector
from .llm import build_planner, Planner, ResilientPlanner
from .schemas import QueryRequest, QueryResponse

def create_app(csv_path: Path | str | None = None, db_path: Path | str | None = None, planner: Planner | None = None) -> FastAPI:
    repo = TicketRepository(csv_path or settings.csv_path, db_path or settings.db_path)
    query_engine = QueryEngine(repo)
    detector = AnomalyDetector(repo)
    chosen_planner = planner or build_planner(settings.llm_provider, settings.ollama_base_url, settings.ollama_model, settings.groq_api_key, settings.groq_model, settings.allow_rule_fallback)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repo.initialize()
        app.state.repo = repo
        app.state.query_engine = query_engine
        app.state.detector = detector
        app.state.planner = chosen_planner
        yield

    app = FastAPI(title="AI Ticket Intelligence API", version="1.0.0", description="Safe LLM-planned analytics over the supplied support ticket dataset.", lifespan=lifespan)

    @app.get("/health")
    def health():
        h = repo.health()
        h.update({"status":"ok","llm_provider":getattr(chosen_planner,"name","unknown")})
        return h

    @app.post("/query", response_model=QueryResponse)
    def query(req: QueryRequest):
        try:
            plan = chosen_planner.plan(req.question)
            backend = getattr(chosen_planner, "last_backend", getattr(chosen_planner,"name","unknown"))
            llm_error = getattr(chosen_planner, "last_error", None)
            if plan.operation == "anomalies":
                result = detector.detect(plan.relative_window)
                counts = result["counts"]
                answer = f"Detected {counts['abnormally_long_resolution']} long-resolution anomaly/anomalies and {counts['unresolved_high_priority_older_than_24h']} stale high-priority unresolved ticket(s)."
                rows = result["details"]["abnormally_long_resolution"] + result["details"]["unresolved_high_priority_older_than_24h"]
                metadata = {"planner_backend": backend, "llm_error": llm_error, "anomaly_summary": result["counts"], "rules": result["rules"]}
            else:
                result = query_engine.execute(plan)
                answer, rows = result["answer"], result["rows"]
                metadata = {**result["metadata"], "planner_backend":backend, "llm_error":llm_error}
            return QueryResponse(question=req.question, plan=plan, answer=answer, rows=rows, metadata=metadata)
        except Exception as e:
            if isinstance(e, (QueryExecutionError, DataValidationError, ValueError)):
                raise HTTPException(status_code=400, detail=str(e))
            raise HTTPException(status_code=503, detail=f"Query planning/execution failed: {type(e).__name__}: {e}")

    @app.get("/anomalies")
    def anomalies(relative_window: str | None = None):
        if relative_window not in {None,"latest_week","latest_month"}:
            raise HTTPException(status_code=400, detail="relative_window must be latest_week or latest_month")
        return detector.detect(relative_window)

    return app

app = create_app()
