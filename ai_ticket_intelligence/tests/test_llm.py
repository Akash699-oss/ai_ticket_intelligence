from app.llm import OllamaPlanner

class FakeResponse:
    def raise_for_status(self):
        return None
    def json(self):
        return {"message":{"content":"{\"operation\":\"count\",\"filters\":[{\"field\":\"status\",\"operator\":\"eq\",\"value\":\"Open\"}],\"metric\":null,\"group_by\":null,\"limit\":50,\"relative_window\":null,\"unresolved_or_over_resolution_hours\":null}"}}

def test_ollama_planner_structured_json(monkeypatch):
    monkeypatch.setattr("app.llm.requests.post", lambda *a, **k: FakeResponse())
    plan=OllamaPlanner("http://localhost:11434","llama3.2:3b").plan("How many tickets are open?")
    assert plan.operation=="count"
    assert plan.filters[0].field=="status"
