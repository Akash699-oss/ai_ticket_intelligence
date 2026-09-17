# Deployment and Submission Guide

This assessment does **not** require a paid/public cloud deployment. The official submission format is a **GitHub repository + README**, and the evaluator must be able to run the system locally at zero cost. The application therefore uses local deployment as the primary path and keeps public-cloud hosting optional.

## 1. Primary evaluator deployment (recommended)

### Prerequisites

- Python 3.11+
- Git
- Ollama

### Install

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Then:

```bash
python -m pip install -r requirements.txt
ollama pull llama3.2:3b
```

Make sure Ollama is running, then run the preflight check:

```bash
python scripts/preflight.py
```

### Single-command startup

```bash
python run.py
```

This starts both required interfaces:

- FastAPI: `http://127.0.0.1:8000`
- Swagger/OpenAPI: `http://127.0.0.1:8000/docs`
- Streamlit UI: `http://127.0.0.1:8501`

### Verify the running system

In a second terminal:

```bash
python scripts/smoke_test.py
python -m pytest -q
```

Expected deterministic values from the supplied CSV include 500 total rows, 31 Critical unresolved tickets, 21 IQR resolution-time outliers, and 80 stale unresolved High/Critical tickets older than 24 hours at the dataset reference timestamp.

## 2. Bind to all interfaces when needed

For a VM, Codespace, Antigravity remote environment, or other forwarded-port setup, set:

Windows PowerShell:

```powershell
$env:API_HOST="0.0.0.0"
$env:UI_HOST="0.0.0.0"
python run.py
```

Linux/macOS:

```bash
API_HOST=0.0.0.0 UI_HOST=0.0.0.0 python run.py
```

Keep Ollama reachable through `OLLAMA_BASE_URL`. Do not expose the Ollama API publicly.

## 3. GitHub submission

Before committing, run:

```bash
python -m pytest -q
git status
```

The repository `.gitignore` excludes `.env`, virtual environments, generated SQLite databases, caches, and editor metadata.

Create and push the repository:

```bash
git init
git add .
git commit -m "Complete AI Engineer assessment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ai-ticket-intelligence.git
git push -u origin main
```

Then submit the GitHub repository link using the subject format required in the assessment document.

## 4. Why local deployment is the primary path

The system uses Ollama by default because the assessment requires an LLM while also requiring zero-cost execution. Public hosting of Ollama generally requires compute resources and is unnecessary for the requested deliverable. The optional Groq free-tier provider exists for environments where a local Ollama process cannot be used.

## 5. Walkthrough readiness

Before the 30-minute walkthrough:

1. Start Ollama and confirm `ollama list` includes `llama3.2:3b`.
2. Run `python scripts/preflight.py`.
3. Run `python -m pytest -q` and confirm all tests pass.
4. Start the project with `python run.py`.
5. Open `/docs` and the Streamlit UI.
6. Run at least these questions:
   - `How many tickets are currently open?`
   - `How many critical tickets are unresolved?`
   - `Which agent resolved the most tickets this month?`
   - `Show me all Critical tickets not resolved within 12 hours.`
   - `Are there any anomalies in resolution times this week?`
7. Be ready to explain that the LLM produces a validated plan but never executes arbitrary SQL or Python.
