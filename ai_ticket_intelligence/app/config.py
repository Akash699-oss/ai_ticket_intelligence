from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    csv_path: Path = Path(os.getenv("DATA_CSV_PATH", ROOT_DIR / "data" / "support_tickets.csv"))
    db_path: Path = Path(os.getenv("SQLITE_PATH", ROOT_DIR / "data" / "tickets.db"))
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama").lower()
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    allow_rule_fallback: bool = os.getenv("ALLOW_RULE_FALLBACK", "true").lower() in {"1","true","yes"}
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    ui_port: int = int(os.getenv("UI_PORT", "8501"))

settings = Settings()
