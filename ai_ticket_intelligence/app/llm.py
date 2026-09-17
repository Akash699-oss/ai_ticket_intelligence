from __future__ import annotations

import json
import re
from typing import Protocol
import requests
from pydantic import ValidationError

from .schemas import QueryPlan

SYSTEM_PROMPT = """You convert customer-support analytics questions into a strict JSON query plan.
Never generate SQL or Python. Return ONLY one JSON object matching this shape:
{
  "operation": one of [count,list,average,group_count,group_average,max_group_count,min_group_average,anomalies],
  "filters": [{"field": allowed_field, "operator": one of [eq,neq,in,not_in,gt,gte,lt,lte,contains,is_null,not_null], "value": any}],
  "metric": null or one of [response_time_hrs,resolution_time_hrs,customer_rating],
  "group_by": null or one of [category,priority,status,agent_id],
  "limit": integer 1..200,
  "relative_window": null or latest_week or latest_month,
  "unresolved_or_over_resolution_hours": null or positive number
}
Allowed fields: ticket_id, created_at, category, priority, status, response_time_hrs, resolution_time_hrs, agent_id, customer_rating, issue_summary.
Important semantics:
- unresolved means status != Resolved.
- 'not resolved within N hours' means unresolved_or_over_resolution_hours=N.
- 'this month' means relative_window=latest_month; 'this week' means latest_week.
- most tickets by group => max_group_count.
- lowest average metric by group => min_group_average.
- anomaly questions => operation=anomalies.
Use canonical values exactly: category Billing/Technical/General; priority Low/Medium/High/Critical; status Open/Resolved/Escalated.
"""

class Planner(Protocol):
    name: str
    def plan(self, question: str) -> QueryPlan: ...

class RuleBasedPlanner:
    name = "rule_fallback"
    def plan(self, question: str) -> QueryPlan:
        q = question.lower().strip()
        filters = []
        if "critical" in q: filters.append({"field":"priority","operator":"eq","value":"Critical"})
        elif "high priority" in q or "high-priority" in q: filters.append({"field":"priority","operator":"eq","value":"High"})
        if "technical" in q: filters.append({"field":"category","operator":"eq","value":"Technical"})
        elif "billing" in q: filters.append({"field":"category","operator":"eq","value":"Billing"})
        elif "general" in q: filters.append({"field":"category","operator":"eq","value":"General"})
        if "currently open" in q or re.search(r"\bopen tickets?\b", q): filters.append({"field":"status","operator":"eq","value":"Open"})
        if "unresolved" in q or "not resolved" in q: filters.append({"field":"status","operator":"neq","value":"Resolved"})
        relative = "latest_week" if "this week" in q else "latest_month" if "this month" in q else None
        sla = None
        m = re.search(r"not resolved within\s+(\d+(?:\.\d+)?)\s*hours?", q)
        if m:
            sla = float(m.group(1))
            filters = [f for f in filters if not (f["field"]=="status" and f["operator"]=="neq")]
        if "anomal" in q: op, metric, group = "anomalies", None, None
        elif "lowest average" in q and "agent" in q: op, metric, group = "min_group_average", "customer_rating", "agent_id"
        elif "resolved the most" in q and "agent" in q:
            op, metric, group = "max_group_count", None, "agent_id"
            filters.append({"field":"status","operator":"eq","value":"Resolved"})
        elif "average" in q and "rating" in q: op, metric, group = "average", "customer_rating", None
        elif q.startswith("show") or q.startswith("list") or "show me" in q: op, metric, group = "list", None, None
        else: op, metric, group = "count", None, None
        return QueryPlan(operation=op, filters=filters, metric=metric, group_by=group, relative_window=relative, unresolved_or_over_resolution_hours=sla, limit=50)

class OllamaPlanner:
    name = "ollama"
    def __init__(self, base_url: str, model: str, timeout: int = 45):
        self.base_url, self.model, self.timeout = base_url.rstrip('/'), model, timeout
    def plan(self, question: str) -> QueryPlan:
        payload = {"model": self.model, "stream": False, "format": "json", "messages": [{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":question}]}
        r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        r.raise_for_status()
        content = r.json()["message"]["content"]
        return QueryPlan.model_validate(json.loads(content))

class GroqPlanner:
    name = "groq"
    def __init__(self, api_key: str, model: str, timeout: int = 45):
        self.api_key, self.model, self.timeout = api_key, model, timeout
    def plan(self, question: str) -> QueryPlan:
        headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"}
        payload={"model":self.model,"temperature":0,"response_format":{"type":"json_object"},"messages":[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":question}]}
        r=requests.post("https://api.groq.com/openai/v1/chat/completions",headers=headers,json=payload,timeout=self.timeout)
        r.raise_for_status()
        return QueryPlan.model_validate(json.loads(r.json()["choices"][0]["message"]["content"]))

class ResilientPlanner:
    def __init__(self, primary: Planner, fallback: Planner | None = None):
        self.primary, self.fallback = primary, fallback
        self.name = primary.name
        self.last_backend = primary.name
        self.last_error: str | None = None
    def plan(self, question: str) -> QueryPlan:
        try:
            plan = self.primary.plan(question)
            self.last_backend, self.last_error = self.primary.name, None
            return plan
        except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError, ValidationError) as e:
            self.last_error = f"{type(e).__name__}: {e}"
            if self.fallback is None:
                raise
            self.last_backend = self.fallback.name
            return self.fallback.plan(question)

def build_planner(provider: str, ollama_base_url: str, ollama_model: str, groq_api_key: str | None, groq_model: str, allow_fallback: bool = True) -> Planner:
    fallback = RuleBasedPlanner() if allow_fallback else None
    if provider == "ollama": return ResilientPlanner(OllamaPlanner(ollama_base_url, ollama_model), fallback)
    if provider == "groq":
        if not groq_api_key: raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        return ResilientPlanner(GroqPlanner(groq_api_key, groq_model), fallback)
    if provider in {"rule","mock"}: return RuleBasedPlanner()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
