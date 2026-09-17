import pandas as pd
import pytest
from app.db import TicketRepository, DataValidationError
from app.query_engine import QueryEngine
from app.schemas import QueryPlan
from app.anomalies import AnomalyDetector

def test_csv_ingestion(repo):
    df=repo.dataframe(); assert len(df)==500; assert pd.api.types.is_datetime64_any_dtype(df.created_at)
    assert df.resolution_time_hrs.isna().sum()==173

def test_data_validation_missing_column(tmp_path, csv_path):
    df=pd.read_csv(csv_path).drop(columns=["priority"]); bad=tmp_path/"bad.csv"; df.to_csv(bad,index=False)
    with pytest.raises(DataValidationError): TicketRepository(bad,tmp_path/"bad.db").initialize()

def test_count_open(repo):
    result=QueryEngine(repo).execute(QueryPlan(operation="count",filters=[{"field":"status","operator":"eq","value":"Open"}]))
    assert result["metadata"]["value"]==111

def test_filter_critical_unresolved(repo):
    plan=QueryPlan(operation="count",filters=[{"field":"priority","operator":"eq","value":"Critical"},{"field":"status","operator":"neq","value":"Resolved"}])
    assert QueryEngine(repo).execute(plan)["metadata"]["value"]==31

def test_average_technical_rating(repo):
    plan=QueryPlan(operation="average",metric="customer_rating",filters=[{"field":"category","operator":"eq","value":"Technical"}])
    assert QueryEngine(repo).execute(plan)["metadata"]["value"]==pytest.approx(3.7404,abs=1e-4)

def test_group_most_resolved_agent(repo):
    plan=QueryPlan(operation="max_group_count",group_by="agent_id",filters=[{"field":"status","operator":"eq","value":"Resolved"}])
    r=QueryEngine(repo).execute(plan); assert {x["agent_id"] for x in r["rows"]}=={"AGT-09","AGT-12"}; assert {x["count"] for x in r["rows"]}=={37}

def test_lowest_average_agent(repo):
    plan=QueryPlan(operation="min_group_average",group_by="agent_id",metric="customer_rating")
    r=QueryEngine(repo).execute(plan); assert r["rows"][0]["agent_id"]=="AGT-08"; assert r["rows"][0]["average_customer_rating"]==pytest.approx(3.48)

def test_anomalies(repo):
    r=AnomalyDetector(repo).detect(); assert r["rules"]["resolution_time_iqr"]["upper_fence_hours"]==pytest.approx(48.15); assert r["counts"]["abnormally_long_resolution"]==21; assert r["counts"]["unresolved_high_priority_older_than_24h"]==80

def test_invalid_field_rejected():
    with pytest.raises(Exception): QueryPlan(operation="count",filters=[{"field":"drop_table","operator":"eq","value":1}])

def test_resolution_sla_semantics(repo):
    plan=QueryPlan(operation="count",filters=[{"field":"priority","operator":"eq","value":"Critical"}],unresolved_or_over_resolution_hours=12)
    assert QueryEngine(repo).execute(plan)["metadata"]["value"]==34

def test_latest_month_group_query(repo):
    plan=QueryPlan(operation="max_group_count",group_by="agent_id",relative_window="latest_month",filters=[{"field":"status","operator":"eq","value":"Resolved"}])
    r=QueryEngine(repo).execute(plan)
    assert r["rows"]==[{"agent_id":"AGT-01","count":16}]
