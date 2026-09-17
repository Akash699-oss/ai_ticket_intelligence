"""Smoke-test a running API instance.

Start the project first with `python run.py`, then run:
    python scripts/smoke_test.py
"""
from __future__ import annotations

import os
import sys

import requests

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[OK] {message}")


def main() -> int:
    health = requests.get(f"{API_URL}/health", timeout=10)
    health.raise_for_status()
    payload = health.json()
    check(payload.get("status") == "ok", "GET /health reports status=ok")
    check(payload.get("rows") == 500, "GET /health reports 500 supplied rows")

    query = requests.post(
        f"{API_URL}/query",
        json={"question": "How many critical tickets are unresolved?"},
        timeout=60,
    )
    query.raise_for_status()
    q_payload = query.json()
    check(q_payload.get("metadata", {}).get("value") == 31, "POST /query returns 31 critical unresolved tickets")
    check("plan" in q_payload, "POST /query exposes the validated plan")

    anomalies = requests.get(f"{API_URL}/anomalies", timeout=20)
    anomalies.raise_for_status()
    a_payload = anomalies.json()
    check(a_payload["counts"]["abnormally_long_resolution"] == 21, "GET /anomalies finds 21 long-resolution outliers")
    check(a_payload["counts"]["unresolved_high_priority_older_than_24h"] == 80, "GET /anomalies finds 80 stale urgent unresolved tickets")

    print("\nSmoke test passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
