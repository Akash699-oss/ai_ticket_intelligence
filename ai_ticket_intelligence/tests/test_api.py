from fastapi.testclient import TestClient

def test_health(app):
    with TestClient(app) as client:
        r=client.get("/health"); assert r.status_code==200; assert r.json()["rows"]==500

def test_query(app):
    with TestClient(app) as client:
        r=client.post("/query",json={"question":"How many critical tickets are unresolved?"}); assert r.status_code==200; assert r.json()["metadata"]["value"]==31

def test_anomalies_endpoint(app):
    with TestClient(app) as client:
        r=client.get("/anomalies"); assert r.status_code==200; assert r.json()["counts"]["abnormally_long_resolution"]==21

def test_invalid_input(app):
    with TestClient(app) as client:
        r=client.post("/query",json={"question":""}); assert r.status_code==422
        r=client.get("/anomalies?relative_window=yesterday"); assert r.status_code==400
