from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from src.core.di_container import Container
import uvicorn
import os
import logging
import requests as http_requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    query: str
    sql_query: Optional[str]
    data: Optional[List[Dict[str, Any]]]
    dashboard_config: Optional[Dict[str, Any]]
    error: Optional[str]


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_checks()
    yield


app = FastAPI(title="Agentic Risk Dashboard API", lifespan=lifespan)

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "llama3.1")
DB_PATH = os.environ.get("DB_PATH", "risk.db")

# Initialize DI Container
container = Container()
container.config.db_path.from_value(DB_PATH)
container.config.llm_base_url.from_value(LLM_BASE_URL)
container.config.llm_model_name.from_value(LLM_MODEL_NAME)


def startup_checks():
    logger.info(f"LLM endpoint : {LLM_BASE_URL}")
    logger.info(f"LLM model    : {LLM_MODEL_NAME}")
    logger.info(f"Database     : {DB_PATH}")

    # Derive Ollama base URL from the OpenAI-compat URL (strip /v1)
    ollama_base = LLM_BASE_URL.rstrip("/")
    if ollama_base.endswith("/v1"):
        ollama_base = ollama_base[:-3]

    try:
        resp = http_requests.get(f"{ollama_base}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        logger.info(f"Ollama available models: {models}")
        if not any(LLM_MODEL_NAME in m for m in models):
            logger.warning(
                f"Model '{LLM_MODEL_NAME}' not found in Ollama. "
                f"Run: ollama pull {LLM_MODEL_NAME}"
            )
        else:
            logger.info(f"Model '{LLM_MODEL_NAME}' is available.")
    except Exception as e:
        logger.error(f"Cannot reach Ollama at {ollama_base}: {e}")


@app.get("/")
def read_root():
    return {"message": "Agentic Risk Dashboard API is running."}


@app.post("/query", response_model=QueryResponse)
def handle_query(request: QueryRequest):
    """Processes a natural language query through the agent workflow."""
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    workflow = container.workflow()
    try:
        result = workflow.process_query(request.query)
    except Exception as e:
        result = {
            "query": request.query,
            "sql_query": None,
            "data": None,
            "dashboard_config": None,
            "error": str(e),
        }

    return QueryResponse(**result)


def start():
    """Starts the FastAPI server."""
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    start()
