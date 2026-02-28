import asyncio
from src.data.sqlite_db import SQLiteDatabase
from src.agents.workflow import LangGraphWorkflow

db = SQLiteDatabase("risk.db")
# Using a widely available default model for testing if ollama is not up.
# We'll mock the LLM or run it if needed. For now, just importing works.
workflow = LangGraphWorkflow(db, base_url="https://api.openai.com/v1", model_name="gpt-3.5-turbo")
print("Agent Workflow initialized successfully.")
