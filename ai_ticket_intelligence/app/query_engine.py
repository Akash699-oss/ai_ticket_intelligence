from __future__ import annotations

from typing import Any
import pandas as pd

from .db import TicketRepository
from .schemas import QueryPlan, FilterCondition

class QueryExecutionError(ValueError):
    pass

def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
    out = out.astype(object).where(pd.notna(out), None)
    return out.to_dict(orient="records")

class QueryEngine:
    def __init__(self, repo: TicketRepository):
        self.repo = repo

    def _apply_filter(self, df: pd.DataFrame, f: FilterCondition) -> pd.DataFrame:
        s = df[f.field]
        op, val = f.operator, f.value
        if f.field == "created_at" and val is not None:
            if op in {"in","not_in"}:
                val = [pd.Timestamp(v) for v in val]
            else:
                val = pd.Timestamp(val)
        if op == "eq": mask = s == val
        elif op == "neq": mask = s != val
        elif op == "in": mask = s.isin(val)
        elif op == "not_in": mask = ~s.isin(val)
        elif op == "gt": mask = s > val
        elif op == "gte": mask = s >= val
        elif op == "lt": mask = s < val
        elif op == "lte": mask = s <= val
        elif op == "contains": mask = s.astype(str).str.contains(str(val), case=False, na=False, regex=False)
        elif op == "is_null": mask = s.isna()
        elif op == "not_null": mask = s.notna()
        else: raise QueryExecutionError(f"Unsupported operator: {op}")
        return df[mask]

    def _apply_plan_filters(self, df: pd.DataFrame, plan: QueryPlan) -> pd.DataFrame:
        for f in plan.filters:
            df = self._apply_filter(df, f)
        ref = self.repo.reference_time
        if plan.relative_window == "latest_week":
            df = df[(df["created_at"] >= ref - pd.Timedelta(days=7)) & (df["created_at"] <= ref)]
        elif plan.relative_window == "latest_month":
            start = ref.to_period("M").start_time
            end = ref.to_period("M").end_time
            df = df[(df["created_at"] >= start) & (df["created_at"] <= end)]
        if plan.unresolved_or_over_resolution_hours is not None:
            h = float(plan.unresolved_or_over_resolution_hours)
            df = df[(df["status"] != "Resolved") | (df["resolution_time_hrs"] > h)]
        return df

    def execute(self, plan: QueryPlan) -> dict[str, Any]:
        if plan.operation == "anomalies":
            raise QueryExecutionError("Use the anomaly service for anomaly plans")
        df = self._apply_plan_filters(self.repo.dataframe(), plan)
        meta = {"matched_rows": int(len(df)), "dataset_rows": int(len(self.repo.dataframe()))}

        if plan.operation == "count":
            value = int(len(df))
            return {"answer": f"{value} ticket(s).", "rows": [], "metadata": {**meta, "value": value}}
        if plan.operation == "list":
            rows = _records(df.head(plan.limit))
            return {"answer": f"Found {len(df)} matching ticket(s); showing {len(rows)}.", "rows": rows, "metadata": meta}
        if plan.operation == "average":
            value = df[plan.metric].mean() if len(df) else float("nan")
            value = None if pd.isna(value) else round(float(value), 4)
            return {"answer": "No matching non-null values." if value is None else f"Average {plan.metric}: {value}.", "rows": [], "metadata": {**meta, "value": value}}
        if plan.operation in {"group_count","max_group_count"}:
            grouped = df.groupby(plan.group_by, dropna=False).size().reset_index(name="count").sort_values(["count",plan.group_by], ascending=[False,True])
            if plan.operation == "max_group_count":
                if grouped.empty: return {"answer":"No matching rows.","rows":[],"metadata":meta}
                maxv = int(grouped["count"].max()); winners = grouped[grouped["count"]==maxv]
                names = ", ".join(map(str,winners[plan.group_by].tolist()))
                return {"answer": f"{names} with {maxv} ticket(s).", "rows": _records(winners), "metadata": meta}
            rows = _records(grouped.head(plan.limit))
            return {"answer": f"Grouped ticket counts by {plan.group_by}.", "rows": rows, "metadata": meta}
        if plan.operation in {"group_average","min_group_average"}:
            grouped = df.groupby(plan.group_by, dropna=False)[plan.metric].mean().dropna().reset_index(name=f"average_{plan.metric}")
            grouped[f"average_{plan.metric}"] = grouped[f"average_{plan.metric}"].round(4)
            grouped = grouped.sort_values([f"average_{plan.metric}",plan.group_by], ascending=[True,True])
            if plan.operation == "min_group_average":
                if grouped.empty: return {"answer":"No matching values.","rows":[],"metadata":meta}
                minv = float(grouped[f"average_{plan.metric}"].min()); winners = grouped[grouped[f"average_{plan.metric}"]==minv]
                names = ", ".join(map(str,winners[plan.group_by].tolist()))
                return {"answer": f"{names} with average {plan.metric} {minv:.4f}.", "rows": _records(winners), "metadata": meta}
            rows = _records(grouped.head(plan.limit))
            return {"answer": f"Grouped average {plan.metric} by {plan.group_by}.", "rows": rows, "metadata": meta}
        raise QueryExecutionError(f"Unsupported operation: {plan.operation}")
