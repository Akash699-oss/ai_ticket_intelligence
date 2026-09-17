# Design Notes

## Core decision
The LLM is an interpreter, not an executor. It may only emit a `QueryPlan` validated by Pydantic. No LLM-produced SQL or Python is ever executed. All calculations run in deterministic Pandas code over data ingested from the supplied CSV and persisted locally to SQLite.

## Historical time semantics
The provided dataset ends on 2024-03-30. Using wall-clock time would make every unresolved historical ticket continuously older and would make test output drift. For reproducible analysis, ticket age and relative windows use `max(created_at)` as the dataset reference time. This assumption is surfaced in `/health`, `/anomalies`, and README. In a live production system, this would be replaced with an injected current clock or a source-system snapshot timestamp.

## Anomaly methods
1. Resolution-time outlier: IQR upper fence = Q3 + 1.5 × IQR, computed from all non-null resolution times.
2. Stale urgent ticket: status != Resolved, priority in {High, Critical}, and age > 24 hours at the dataset reference time.

## Reliability
Ollama is the default LLM provider. If unavailable and `ALLOW_RULE_FALLBACK=true`, a narrow deterministic planner handles common assessment questions so the UI/API remain demonstrable. Metadata reveals whether the LLM or fallback produced the plan. Set `ALLOW_RULE_FALLBACK=false` to enforce LLM-only behavior.

## Security
- Strict operation, field, metric, group and operator allow-lists
- Pydantic validation of LLM JSON
- No `eval`, `exec`, shell execution, or arbitrary SQL
- Bound result limits (max 200 rows)
