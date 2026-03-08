# Agentic Risk Dashboard

An experiential project using AI agents to create dynamic risk dashboards for traders.

## Overview

The Agentic Risk Dashboard is a modular, interface-driven, and API-first application that leverages a multi-agent workflow orchestrated using LangGraph. The project is designed to generate dynamic insights and visualizations for traders.

## Tech Stack

- **Backend:** FastAPI
- **Frontend:** Streamlit
- **Dependency Injection:** `dependency-injector`
- **Agent Orchestration:** LangGraph
- **LLM Integration:** Local Ollama models (via OpenAI API format)
- **Data Storage:** SQLite / DuckDB (local development), using abstract database interfaces (e.g., `IDatabase`) to allow future migrations (e.g., to ClickHouse)
- **Containerization:** Docker & Docker Compose
- **Deployment:** GitHub Actions to GitHub Container Registry (GHCR)

## Architecture

The application is split into two primary services:
1. **API (`api`):** A FastAPI backend that hosts the agentic workflow and serves data and insights.
2. **Frontend (`frontend`):** A Streamlit application that provides an interactive dashboard, connecting to the API via the internal Docker network.

## Getting Started

### Prerequisites

- Python 3.9+ with [uv](https://github.com/astral-sh/uv)
- [Ollama](https://ollama.com/) for local LLM inference
- Docker & Docker Compose (optional, for containerized execution)

### 1. Set Up Ollama

Install Ollama and pull the required model:

```bash
# Install Ollama (Linux/macOS)
curl -fsSL https://ollama.com/install.sh | sh

# Start the Ollama server (keep this running in a dedicated terminal)
ollama serve

# Pull the default model (~4GB, one-time download)
ollama pull llama3.1
```

The API expects Ollama at `http://localhost:11434`. Override with env vars if needed:

```bash
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_MODEL_NAME=llama3.1
```

### 2. Run Locally

Run each service in a separate terminal:

```bash
# Install dependencies
uv sync

# Generate mock data
uv run python -m src.data.generator

# Terminal 1 — FastAPI backend
uv run python -m src.api.app

# Terminal 2 — Streamlit frontend
uv run streamlit run src/frontend/app.py --server.port 8501 --server.address 0.0.0.0
```

- API is available at: `http://localhost:8000`
- Frontend is available at: `http://localhost:8501`

### Running with Docker Compose

To run the application using Docker Compose:

```bash
docker-compose up --build
```
This will spin up both the `api` and `frontend` containers. By default, the API container is configured to look for a local Ollama instance on `host.docker.internal:11434`. You can adjust environment variables in `docker-compose.yml` if your LLM is hosted elsewhere.

## Testing

You can run a quick initialization test to ensure the agent workflow is set up correctly:

```bash
python test_agent.py
```

## Deployment

Deployment is fully automated using GitHub Actions. Upon pushing to the main branch, Docker images for both the API and frontend are built and pushed to the GitHub Container Registry (GHCR).
