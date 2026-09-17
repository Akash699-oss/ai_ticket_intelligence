from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

ALLOWED_FIELDS = {
    "ticket_id", "created_at", "category", "priority", "status",
    "response_time_hrs", "resolution_time_hrs", "agent_id",
    "customer_rating", "issue_summary",
}
NUMERIC_FIELDS = {"response_time_hrs", "resolution_time_hrs", "customer_rating"}
GROUPABLE_FIELDS = {"category", "priority", "status", "agent_id"}

class FilterCondition(BaseModel):
    field: str
    operator: Literal["eq","neq","in","not_in","gt","gte","lt","lte","contains","is_null","not_null"]
    value: Any = None

    @field_validator("field")
    @classmethod
    def field_allowed(cls, v: str) -> str:
        if v not in ALLOWED_FIELDS:
            raise ValueError(f"Unsupported field: {v}")
        return v

    @model_validator(mode="after")
    def validate_value(self):
        if self.operator in {"is_null","not_null"}:
            return self
        if self.value is None:
            raise ValueError(f"Operator {self.operator} requires a value")
        if self.operator in {"in","not_in"} and not isinstance(self.value, list):
            raise ValueError(f"Operator {self.operator} requires a list value")
        return self

class QueryPlan(BaseModel):
    operation: Literal[
        "count","list","average","group_count","group_average",
        "max_group_count","min_group_average","anomalies"
    ]
    filters: list[FilterCondition] = Field(default_factory=list)
    metric: str | None = None
    group_by: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    relative_window: Literal["latest_week","latest_month"] | None = None
    unresolved_or_over_resolution_hours: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_plan(self):
        if self.operation in {"average","group_average","min_group_average"}:
            if self.metric not in NUMERIC_FIELDS:
                raise ValueError(f"metric must be one of {sorted(NUMERIC_FIELDS)}")
        elif self.metric is not None and self.metric not in NUMERIC_FIELDS:
            raise ValueError(f"Unsupported metric: {self.metric}")
        if self.operation in {"group_count","group_average","max_group_count","min_group_average"}:
            if self.group_by not in GROUPABLE_FIELDS:
                raise ValueError(f"group_by must be one of {sorted(GROUPABLE_FIELDS)}")
        elif self.group_by is not None and self.group_by not in GROUPABLE_FIELDS:
            raise ValueError(f"Unsupported group_by: {self.group_by}")
        return self

class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)

class QueryResponse(BaseModel):
    question: str
    plan: QueryPlan
    answer: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
