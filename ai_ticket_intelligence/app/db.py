from __future__ import annotations

import sqlite3
from pathlib import Path
import pandas as pd

REQUIRED_COLUMNS = [
    "ticket_id","created_at","category","priority","status",
    "response_time_hrs","resolution_time_hrs","agent_id",
    "customer_rating","issue_summary",
]
VALID_CATEGORY = {"Billing","Technical","General"}
VALID_PRIORITY = {"Low","Medium","High","Critical"}
VALID_STATUS = {"Open","Resolved","Escalated"}

class DataValidationError(ValueError):
    pass

class TicketRepository:
    def __init__(self, csv_path: Path | str, db_path: Path | str):
        self.csv_path = Path(csv_path)
        self.db_path = Path(db_path)
        self._df: pd.DataFrame | None = None

    def initialize(self) -> None:
        df = self._read_and_validate_csv()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            persist = df.copy()
            persist["created_at"] = persist["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
            persist.to_sql("tickets", conn, if_exists="replace", index=False)
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_ticket_id ON tickets(ticket_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON tickets(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_priority ON tickets(priority)")
        self._df = df

    def _read_and_validate_csv(self) -> pd.DataFrame:
        if not self.csv_path.exists():
            raise DataValidationError(f"CSV not found: {self.csv_path}")
        df = pd.read_csv(self.csv_path)
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        extra = [c for c in df.columns if c not in REQUIRED_COLUMNS]
        if missing:
            raise DataValidationError(f"Missing required columns: {missing}")
        if extra:
            df = df[REQUIRED_COLUMNS]
        if df.empty:
            raise DataValidationError("CSV is empty")
        if df["ticket_id"].duplicated().any():
            raise DataValidationError("ticket_id must be unique")

        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        if df["created_at"].isna().any():
            bad = int(df["created_at"].isna().sum())
            raise DataValidationError(f"Invalid created_at values: {bad}")

        for col in ["response_time_hrs","resolution_time_hrs","customer_rating"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if df["response_time_hrs"].isna().any():
            raise DataValidationError("response_time_hrs contains missing/invalid values")
        invalid_rating = df["customer_rating"].dropna().loc[lambda s: ~s.between(1,5)]
        if not invalid_rating.empty:
            raise DataValidationError("customer_rating must be between 1 and 5")

        if not set(df["category"].dropna().unique()).issubset(VALID_CATEGORY):
            raise DataValidationError("Unexpected category value")
        if not set(df["priority"].dropna().unique()).issubset(VALID_PRIORITY):
            raise DataValidationError("Unexpected priority value")
        if not set(df["status"].dropna().unique()).issubset(VALID_STATUS):
            raise DataValidationError("Unexpected status value")

        unresolved = df["status"] != "Resolved"
        # Unresolved tickets are expected to have null resolution/rating in this dataset.
        # Resolved rows should contain both so aggregation semantics remain meaningful.
        if df.loc[~unresolved, "resolution_time_hrs"].isna().any():
            raise DataValidationError("Resolved tickets must have resolution_time_hrs")
        if df.loc[~unresolved, "customer_rating"].isna().any():
            raise DataValidationError("Resolved tickets must have customer_rating")
        return df

    def dataframe(self) -> pd.DataFrame:
        if self._df is None:
            self.initialize()
        return self._df.copy()

    @property
    def reference_time(self) -> pd.Timestamp:
        return self.dataframe()["created_at"].max()

    def health(self) -> dict:
        df = self.dataframe()
        return {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "reference_time": self.reference_time.isoformat(),
            "csv_path": str(self.csv_path),
            "db_path": str(self.db_path),
        }
