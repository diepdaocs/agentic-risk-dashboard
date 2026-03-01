from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from src.core.di_container import Container
from src.core.interfaces import IAgentWorkflow
import uvicorn
import os

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    sql_query: Optional[str]
    data: Optional[List[Dict[str, Any]]]
    dashboard_config: Optional[Dict[str, Any]]
    error: Optional[str]

app = FastAPI(title="Agentic Risk Dashboard API")

# Initialize DI Container
container = Container()
# Set default config for local ollama
container.config.db_path.from_value(os.environ.get("DB_PATH", "risk.db"))
container.config.llm_base_url.from_value(os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"))
container.config.llm_model_name.from_value(os.environ.get("LLM_MODEL_NAME", "llama3.1"))

app.container = container

@app.get("/")
def read_root():
    return {"message": "Agentic Risk Dashboard API is running."}

from dependency_injector.wiring import Provide, inject

app.container.wire(modules=[__name__])

@app.post("/query", response_model=QueryResponse)
@inject
def handle_query(request: QueryRequest, workflow: IAgentWorkflow = Depends(Provide[Container.workflow])):
    """Processes a natural language query through the agent workflow."""
    if not request.query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    result = workflow.process_query(request.query)

    if result.get("error"):
        # We don't want to throw an HTTP 500 for a bad query, just return the error gracefully in JSON.
        pass

    return QueryResponse(**result)

def start():
    """Starts the FastAPI server."""
    uvicorn.run("src.api.app:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    start()
