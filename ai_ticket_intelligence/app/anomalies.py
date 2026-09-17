from __future__ import annotations

from typing import Any
import pandas as pd
from .db import TicketRepository
from .query_engine import _records

class AnomalyDetector:
    def __init__(self, repo: TicketRepository):
        self.repo = repo

    def detect(self, relative_window: str | None = None) -> dict[str, Any]:
        all_df = self.repo.dataframe()
        ref = self.repo.reference_time
        df = all_df
        if relative_window == "latest_week":
            df = df[(df.created_at >= ref - pd.Timedelta(days=7)) & (df.created_at <= ref)]
        elif relative_window == "latest_month":
            start, end = ref.to_period("M").start_time, ref.to_period("M").end_time
            df = df[(df.created_at >= start) & (df.created_at <= end)]

        resolved_times = all_df["resolution_time_hrs"].dropna()
        q1 = float(resolved_times.quantile(0.25))
        q3 = float(resolved_times.quantile(0.75))
        iqr = q3 - q1
        upper = q3 + 1.5 * iqr
        long_res = df[df["resolution_time_hrs"] > upper].copy()

        age_hours = (ref - df["created_at"]).dt.total_seconds() / 3600.0
        old_unresolved = df[(df["status"] != "Resolved") & df["priority"].isin(["High","Critical"]) & (age_hours > 24)].copy()
        old_unresolved["age_hours_at_reference"] = age_hours.loc[old_unresolved.index].round(2)

        return {
            "reference_time": ref.isoformat(),
            "relative_window": relative_window,
            "counts": {
                "abnormally_long_resolution": int(len(long_res)),
                "unresolved_high_priority_older_than_24h": int(len(old_unresolved)),
                "total_flags": int(len(long_res) + len(old_unresolved)),
            },
            "rules": {
                "resolution_time_iqr": {"q1": round(q1,4), "q3": round(q3,4), "iqr": round(iqr,4), "upper_fence_hours": round(upper,4), "rule": "resolution_time_hrs > Q3 + 1.5*IQR"},
                "stale_high_priority": {"age_threshold_hours": 24, "priorities": ["High","Critical"], "status_rule": "status != Resolved", "age_reference": "max(created_at) in dataset for reproducible historical analysis"},
            },
            "details": {
                "abnormally_long_resolution": _records(long_res),
                "unresolved_high_priority_older_than_24h": _records(old_unresolved),
            },
        }
