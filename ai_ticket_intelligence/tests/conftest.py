from pathlib import Path
import pytest
from app.db import TicketRepository
from app.llm import RuleBasedPlanner
from app.main import create_app

@pytest.fixture(scope="session")
def csv_path():
    return Path(__file__).resolve().parents[1] / "data" / "support_tickets.csv"

@pytest.fixture
def repo(tmp_path, csv_path):
    r=TicketRepository(csv_path,tmp_path/"tickets.db"); r.initialize(); return r

@pytest.fixture
def app(tmp_path, csv_path):
    return create_app(csv_path,tmp_path/"api.db",planner=RuleBasedPlanner())
