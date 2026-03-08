# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Local Development
```bash
uv sync                       # Create .venv and install all dependencies

# Generate mock data
uv run python -m src.data.generator

# Run services separately (in different terminals)
uv run python -m src.api.app                             # FastAPI backend (port 8000)
uv run streamlit run src/frontend/app.py --server.port 8501 --server.address 0.0.0.0  # Frontend (port 8501)
```

### Testing
```bash
uv run python test_agent.py   # Smoke test: verifies workflow initialization (uses OpenAI API, not Ollama)
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Ollama OpenAI-compatible endpoint |
| `LLM_MODEL_NAME` | `llama3.1` | Model for inference |
| `DB_PATH` | `risk.db` | SQLite database path |
| `API_URL` | `http://localhost:8000/query` | Frontend → API endpoint (local) |
| `FRONTEND_API_URL` | `http://api:8000/query` | Frontend → API endpoint (Docker) |

### Docker
```bash
docker-compose up --build   # Runs API + frontend; generates data on API startup
```

## Architecture

Two services, one codebase:
- **`src/api/app.py`** — FastAPI backend; exposes `POST /query` endpoint
- **`src/frontend/app.py`** — Streamlit chat UI; calls the API and renders dynamic charts

### Agent Workflow (`src/agents/workflow.py`)

A LangGraph `StateGraph` with three sequential nodes:

1. **`text2sql`** — LLM converts natural language → SQL SELECT
2. **`execute_sql`** — Runs SQL against SQLite; short-circuits to `END` on error
3. **`text2dashboard`** — LLM converts data sample → JSON dashboard config (`{title, panels[{type, x_axis, y_axis, color}]}`)

The LLM defaults to a local Ollama instance (`llama3.1` via OpenAI-compatible API). Configured via env vars: `LLM_BASE_URL`, `LLM_MODEL_NAME`.

### Dependency Injection (`src/core/di_container.py`)

Uses `dependency-injector`. The `Container` wires `SQLiteDatabase` → `LangGraphWorkflow` → FastAPI route. Config sourced from env vars: `DB_PATH`, `LLM_BASE_URL`, `LLM_MODEL_NAME`.

### Interfaces (`src/core/interfaces.py`)

Two abstract base classes:
- **`IDatabase`**: `execute_query(sql) → List[Dict]`, `get_schema_info() → str`
- **`IAgentWorkflow`**: `process_query(user_query) → Dict`

The SQLite implementation (`src/data/sqlite_db.py`) is the only current `IDatabase`. These interfaces allow swapping backends (e.g., ClickHouse) without touching agent or API code.

### Data Model (`src/data/generator.py`)

SQLite database (`risk.db`) with two tables:
- **`trades`**: `trade_id, desk, trader_name, asset_class, instrument, quantity, price, notional, trade_date`
- **`risk_metrics`**: `trade_id, calc_date, pnl, dv01, delta, gamma, vega`

Desks: `FX Spot`, `Rates`, `Options`, `Credit`. Run `python -m src.data.generator` to populate.

### Dashboard Config Format

The `text2dashboard` node produces JSON consumed by the Streamlit frontend:
```json
{
  "title": "...",
  "panels": [
    { "type": "bar|line|scatter|table", "title": "...", "x_axis": "col", "y_axis": "col", "color": "col" }
  ]
}
```
