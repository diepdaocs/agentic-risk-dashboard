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

- Python 3.9+
- Docker & Docker Compose (optional, for containerized execution)
- [Ollama](https://ollama.com/) (if running models locally)

### Running Locally

To run both the FastAPI backend and Streamlit frontend locally concurrently, you can use the provided bash script:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
chmod +x run.sh
./run.sh
```
This will start the FastAPI backend and then launch the Streamlit app.
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
