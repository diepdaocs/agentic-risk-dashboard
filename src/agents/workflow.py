from typing import Dict, Any, List, TypedDict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
import json

from src.core.interfaces import IAgentWorkflow, IDatabase

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
        prompt = f"""You are a specialized Text2SQL agent for a financial risk system.
Your task is to convert the user's natural language query into a valid SQL query for SQLite.
Here is the database schema:
{state['schema']}

Rules:
1. ONLY return the SQL query, nothing else. No markdown formatting, no explanations.
2. The query must be a valid SELECT statement. Do not mutate the database.
3. Only use tables and columns defined in the schema.

User query: {state['query']}
SQL Query:"""

        try:
            response = self.llm.invoke([SystemMessage(content=prompt)])
            sql_query = response.content.strip()
            # remove formatting if llm disobeys
            if sql_query.startswith("```sql"):
                sql_query = sql_query[6:]
            if sql_query.endswith("```"):
                sql_query = sql_query[:-3]
            sql_query = sql_query.strip()
            return {"sql_query": sql_query}
        except Exception as e:
            return {"error": f"Failed to generate SQL: {str(e)}"}

    def node_execute_sql(self, state: AgentState) -> Dict[str, Any]:
        """Executes the generated SQL query."""
        if state.get("error"):
            return state

        sql_query = state.get("sql_query")
        if not sql_query:
            return {"error": "No SQL query generated."}

        data = self.db.execute_query(sql_query)

        # Check if error returned from db
        if data and isinstance(data, list) and len(data) > 0 and "error" in data[0]:
            return {"error": f"SQL Execution Error: {data[0]['error']}"}

        return {"data": data}

    def node_text2dashboard(self, state: AgentState) -> Dict[str, Any]:
        """Agent that takes SQL data and generates a dashboard configuration."""
        if state.get("error"):
            return state

        data_preview = str(state.get("data", [])[:5]) # show max 5 rows to not overflow context

        prompt = f"""You are a Text2Dashboard agent. Your job is to decide the best way to visualize a dataset for a trader.
You are given the user's original query and a sample of the data returned by the database.

User Query: {state['query']}
Data Sample (first few rows):
{data_preview}

Based on this data, create a JSON configuration for a dashboard view. The JSON must follow this exact format:
{{
    "title": "A descriptive title for the dashboard",
    "panels": [
        {{
            "type": "chart_type",
            "title": "Panel Title",
            "x_axis": "column_name_for_x",
            "y_axis": "column_name_for_y",
            "color": "optional_column_for_color_grouping"
        }}
    ]
}}
Available chart types: "bar", "line", "table", "scatter"

Rules:
1. ONLY return valid JSON. No markdown formatting, no explanations.
2. Map the x_axis and y_axis to actual column names present in the data sample.
3. If it's a simple aggregation, a "bar" chart is usually good. Time series should be "line".
"""

        try:
            response = self.llm.invoke([SystemMessage(content=prompt)])
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
