from typing import Dict, Any, List, TypedDict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
import json
import logging

from src.core.interfaces import IAgentWorkflow, IDatabase

logger = logging.getLogger(__name__)

# Define our State
class AgentState(TypedDict):
    query: str
    schema: str
    sql_query: Optional[str]
    data: Optional[List[Dict[str, Any]]]
    dashboard_config: Optional[Dict[str, Any]]
    error: Optional[str]

class LangGraphWorkflow(IAgentWorkflow):
    def __init__(self, db: IDatabase, base_url: str = "http://localhost:11434/v1", model_name: str = "llama3.1"):
        self.db = db
        # Set up LLM pointing to Ollama by default
        self.llm = ChatOpenAI(
            base_url=base_url,
            api_key="ollama", # required but not used by local ollama
            model=model_name,
            temperature=0,
        )

        # Build graph
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("text2sql", self.node_text2sql)
        workflow.add_node("execute_sql", self.node_execute_sql)
        workflow.add_node("text2dashboard", self.node_text2dashboard)

        # Set edges
        workflow.set_entry_point("text2sql")
        workflow.add_edge("text2sql", "execute_sql")

        # Conditional edge: if error executing SQL, stop. Otherwise, go to dashboard.
        def router(state: AgentState):
            if state.get("error"):
                return END
            return "text2dashboard"

        workflow.add_conditional_edges("execute_sql", router)
        workflow.add_edge("text2dashboard", END)

        self.app = workflow.compile()

    def process_query(self, user_query: str) -> Dict[str, Any]:
        """Runs the langgraph pipeline."""
        schema = self.db.get_schema_info()
        initial_state = {
            "query": user_query,
            "schema": schema,
            "sql_query": None,
            "data": None,
            "dashboard_config": None,
            "error": None
        }

        final_state = self.app.invoke(initial_state)

        return {
            "query": final_state["query"],
            "sql_query": final_state.get("sql_query"),
            "data": final_state.get("data"),
            "dashboard_config": final_state.get("dashboard_config"),
            "error": final_state.get("error")
        }

    def node_text2sql(self, state: AgentState) -> Dict[str, Any]:
        """Agent that translates natural language to SQL."""
        system_prompt = f"""You are a Text2SQL agent for a financial risk system using SQLite.
Convert the user's natural language query into a valid SQL SELECT statement.

Database schema:
{state['schema']}

Rules:
1. Return ONLY the raw SQL query. No markdown, no code blocks, no explanations.
2. Only SELECT statements are allowed. Never INSERT, UPDATE, DELETE, or DROP.
3. Only use table and column names that exist exactly as listed in the schema above.
4. Never use column aliases (no AS keyword). Use the exact column names from the schema.
5. For date filtering, use: date(column) >= date('now', '-7 days').
6. Always use explicit column names in SELECT, never SELECT *."""

        try:
            logger.info(f"[text2sql] Invoking LLM for query: {state['query']!r}")
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=state['query']),
            ])
            logger.info(f"[text2sql] Raw LLM response: {response.content!r}")
            sql_query = response.content.strip()
            # remove formatting if llm disobeys
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
            sql_query = sql_query.strip()
            logger.info(f"[text2sql] Generated SQL: {sql_query!r}")
            return {"sql_query": sql_query}
        except Exception as e:
            logger.error(f"[text2sql] Exception: {e}", exc_info=True)
            return {"error": f"Failed to generate SQL: {str(e)}"}

    def node_execute_sql(self, state: AgentState) -> Dict[str, Any]:
        """Executes the generated SQL query."""
        if state.get("error"):
            logger.warning(f"[execute_sql] Skipping due to prior error: {state['error']}")
            return state

        sql_query = state.get("sql_query")
        if not sql_query:
            logger.error("[execute_sql] sql_query is empty or None")
            return {"error": "No SQL query generated."}

        logger.info(f"[execute_sql] Running SQL: {sql_query!r}")
        data = self.db.execute_query(sql_query)

        # Check if error returned from db
        if data and isinstance(data, list) and len(data) > 0 and "error" in data[0]:
            logger.error(f"[execute_sql] DB error: {data[0]['error']}")
            return {"error": f"SQL Execution Error: {data[0]['error']}"}

        logger.info(f"[execute_sql] Returned {len(data)} rows")
        return {"data": data}

    def node_text2dashboard(self, state: AgentState) -> Dict[str, Any]:
        """Agent that takes SQL data and generates a dashboard configuration."""
        if state.get("error"):
            return state

        data = state.get("data", [])
        columns = list(data[0].keys()) if data else []
        data_preview = json.dumps(data[:3], indent=2)

        system_prompt = f"""You are a Text2Dashboard agent for a financial risk system.
Given a user query and query results, return a JSON dashboard configuration.

CRITICAL: The available column names are EXACTLY: {columns}
You MUST only use these exact column names in x_axis, y_axis, and color fields. Do not invent or rename columns.

Output format (return ONLY this JSON, no markdown, no explanation):
{{
    "title": "descriptive dashboard title",
    "panels": [
        {{
            "type": "bar|line|scatter|table",
            "title": "panel title",
            "x_axis": "exact_column_name",
            "y_axis": "exact_column_name",
            "color": "exact_column_name_or_null"
        }}
    ]
}}

Chart selection guide:
- bar: aggregations by category (e.g. PnL by desk)
- line: time series data
- scatter: two numeric columns to compare
- table: detailed row-level data or when unsure"""

        human_prompt = f"""User Query: {state['query']}

Available columns: {columns}

Data sample:
{data_preview}"""

        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt),
            ])
            content = response.content.strip()
            # remove markdown formatting if any
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            config = json.loads(content)
            return {"dashboard_config": config}
        except Exception as e:
            return {"error": f"Failed to generate dashboard config: {str(e)}\nRaw Response: {response.content}"}
