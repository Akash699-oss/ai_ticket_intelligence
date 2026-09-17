"""Local preflight check before evaluator submission.

Usage:
    python scripts/preflight.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.db import TicketRepository  # noqa: E402

REQUIRED_IMPORTS = ["fastapi", "uvicorn", "pandas", "pydantic", "requests", "streamlit", "pytest", "httpx"]


def main() -> int:
    print("AI Ticket Intelligence — deployment preflight")
    print("=" * 52)

    missing = [name for name in REQUIRED_IMPORTS if importlib.util.find_spec(name) is None]
    if missing:
        print("[FAIL] Missing Python packages:", ", ".join(missing))
        print("       Run: python -m pip install -r requirements.txt")
        return 1
    print("[OK]   Required Python packages are importable")

    if not settings.csv_path.exists():
        print(f"[FAIL] Dataset not found: {settings.csv_path}")
        return 1

    with tempfile.TemporaryDirectory() as temp_dir:
        repo = TicketRepository(settings.csv_path, Path(temp_dir) / "tickets.db")
        repo.initialize()
        health = repo.health()
    print(f"[OK]   Dataset validated: {health['rows']} rows")
    print(f"[OK]   Historical reference time: {health['reference_time']}")

    if settings.llm_provider == "ollama":
        try:
            response = requests.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=3)
            response.raise_for_status()
            models = [item.get("name", "") for item in response.json().get("models", [])]
            print(f"[OK]   Ollama reachable at {settings.ollama_base_url}")
            if any(name == settings.ollama_model or name.startswith(f"{settings.ollama_model}:") for name in models):
                print(f"[OK]   Ollama model available: {settings.ollama_model}")
            else:
                print(f"[WARN] Ollama model not listed: {settings.ollama_model}")
                print(f"       Run: ollama pull {settings.ollama_model}")
        except requests.RequestException as exc:
            print(f"[WARN] Ollama is not reachable: {exc}")
            print("       Start Ollama before the walkthrough. The rule fallback may still handle common demo questions.")
    elif settings.llm_provider == "groq":
        if settings.groq_api_key:
            print("[OK]   Groq provider selected and GROQ_API_KEY is present")
        else:
            print("[FAIL] Groq provider selected but GROQ_API_KEY is missing")
            return 1
    else:
        print(f"[WARN] Planner provider is {settings.llm_provider!r}; assessment submission should normally use Ollama or Groq")

    print("\nPreflight complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
