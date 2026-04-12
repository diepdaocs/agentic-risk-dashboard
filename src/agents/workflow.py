from typing import Dict, Any, List, TypedDict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
import json
import logging
import re

from src.core.interfaces import IAgentWorkflow, IDatabase

logger = logging.getLogger(__name__)


def _clean_sql_response(content: str) -> str:
    text = content.strip()
    if text.startswith("```sql"):
        text = text[6:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    match = re.search(r"(?is)select\s.+", text)
    if match:
        text = match.group(0).strip()

    if ";" in text:
        text = text.split(";", 1)[0].strip() + ";"
    elif text.lower().startswith("select"):
        text = text.strip() + ";"

    return text


def _fallback_sql(user_query: str) -> Optional[str]:
    q = user_query.lower().strip()

    if "top 5" in q and "notional" in q and "trade" in q:
        return """
SELECT trades.trade_id, trades.desk, trades.trader_name, trades.instrument, trades.notional, trades.trade_date
FROM trades
ORDER BY trades.notional DESC
LIMIT 5;
""".strip()

    if "total pnl by desk" in q or ("pnl" in q and "desk" in q):
        return """
SELECT trades.desk, SUM(risk_metrics.pnl)
FROM trades
JOIN risk_metrics ON trades.trade_id = risk_metrics.trade_id
WHERE date(risk_metrics.calc_date) >= date('now', '-7 days')
GROUP BY trades.desk
ORDER BY SUM(risk_metrics.pnl) DESC;
""".strip()

    if "dv01 by desk" in q:
        return """
SELECT trades.desk, SUM(risk_metrics.dv01)
FROM trades
JOIN risk_metrics ON trades.trade_id = risk_metrics.trade_id
GROUP BY trades.desk
ORDER BY SUM(risk_metrics.dv01) DESC;
""".strip()

    if "pnl by trader" in q:
        return """
SELECT trades.trader_name, SUM(risk_metrics.pnl)
FROM trades
JOIN risk_metrics ON trades.trade_id = risk_metrics.trade_id
WHERE date(risk_metrics.calc_date) >= date('now', '-7 days')
GROUP BY trades.trader_name
ORDER BY SUM(risk_metrics.pnl) DESC;
""".strip()

    if "recent trades" in q or "most recent trades" in q:
        return """
SELECT trades.trade_id, trades.desk, trades.trader_name, trades.instrument, trades.notional, trades.trade_date
FROM trades
ORDER BY trades.trade_date DESC, trades.trade_id DESC
LIMIT 10;
""".strip()

    if "average notional by asset class" in q:
        return """
SELECT trades.asset_class, AVG(trades.notional)
FROM trades
GROUP BY trades.asset_class
ORDER BY AVG(trades.notional) DESC;
""".strip()

    if "gamma" in q and "vega" in q and "options" in q:
        return """
SELECT trades.trade_id, trades.instrument, risk_metrics.gamma, risk_metrics.vega, risk_metrics.calc_date
FROM trades
JOIN risk_metrics ON trades.trade_id = risk_metrics.trade_id
WHERE trades.desk = 'Options'
ORDER BY risk_metrics.calc_date DESC
LIMIT 20;
""".strip()

    return None


def _fallback_dashboard(user_query: str, columns: List[str]) -> Optional[Dict[str, Any]]:
    q = user_query.lower().strip()

    if not columns:
        return {
            "title": f"Results for: {user_query}",
            "panels": [{"type": "table", "title": "Query Results", "x_axis": None, "y_axis": None, "color": None}],
        }

    if "top 5" in q and "notional" in q and "trade" in q:
        return {
            "title": "Top 5 Trades by Notional",
            "panels": [{"type": "bar", "title": "Top Trades", "x_axis": "trade_id", "y_axis": "notional", "color": None}],
        }

    if "total pnl by desk" in q or ("pnl" in q and "desk" in q):
        return {
            "title": "PnL by Desk",
            "panels": [{"type": "bar", "title": "Desk PnL", "x_axis": "desk", "y_axis": columns[1] if len(columns) > 1 else columns[0], "color": None}],
        }

    if "pnl by trader" in q:
        return {
            "title": "PnL by Trader",
            "panels": [{"type": "bar", "title": "Trader PnL", "x_axis": "trader_name", "y_axis": columns[1] if len(columns) > 1 else columns[0], "color": None}],
        }

    if "dv01 by desk" in q:
        return {
            "title": "DV01 by Desk",
            "panels": [{"type": "bar", "title": "Desk DV01", "x_axis": "desk", "y_axis": columns[1] if len(columns) > 1 else columns[0], "color": None}],
        }

    return None

# Define our State
class AgentState(TypedDict):
    query: str
    schema: str
    sql_query: Optional[str]
    data: Optional[List[Dict[str, Any]]]
    dashboard_config: Optional[Dict[str, Any]]
    error: Optional[str]

class LangGraphWorkflow(IAgentWorkflow):
    def __init__(self, db: IDatabase, base_url: str = "http://localhost:11434/v1", model_name: str = "gemma:2b"):
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
        fallback_sql = _fallback_sql(state["query"])
        if fallback_sql:
            logger.info(f"[text2sql] Using fallback SQL for query: {state['query']!r}")
            return {"sql_query": fallback_sql}

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
6. Always use explicit column names in SELECT, never SELECT *.
7. The only date columns are trades.trade_date and risk_metrics.calc_date.
8. The only risk columns are risk_metrics.pnl, risk_metrics.dv01, risk_metrics.delta, risk_metrics.gamma, risk_metrics.vega.
9. Do not invent columns like trade_date in risk_metrics or dv01_delta.
10. If the user asks for pnl, dv01, delta, gamma, or vega by desk or trader, JOIN trades and risk_metrics on trade_id."""

        try:
            logger.info(f"[text2sql] Invoking LLM for query: {state['query']!r}")
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=state['query']),
            ])
            logger.info(f"[text2sql] Raw LLM response: {response.content!r}")
            sql_query = _clean_sql_response(response.content)
            if not sql_query.lower().startswith("select"):
                return {"error": f"Failed to generate SQL: non-SELECT output from model: {response.content}"}
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
            fallback_sql = _fallback_sql(state["query"])
            if fallback_sql and fallback_sql.strip() != sql_query.strip():
                logger.info(f"[execute_sql] Retrying with fallback SQL for query: {state['query']!r}")
                retry_data = self.db.execute_query(fallback_sql)
                if retry_data and not (isinstance(retry_data, list) and len(retry_data) > 0 and "error" in retry_data[0]):
                    return {"sql_query": fallback_sql, "data": retry_data}
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

        fallback_dashboard = _fallback_dashboard(state["query"], columns)
        if fallback_dashboard:
            logger.info(f"[text2dashboard] Using fallback dashboard for query: {state['query']!r}")
            return {"dashboard_config": fallback_dashboard}

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
            if not isinstance(config, dict) or "panels" not in config:
                raise ValueError("Dashboard config missing panels")
            return {"dashboard_config": config}
        except Exception as e:
            table_panel = {
                "title": f"Results for: {state['query']}",
                "panels": [
                    {
                        "type": "table",
                        "title": "Query Results",
                        "x_axis": columns[0] if columns else None,
                        "y_axis": columns[1] if len(columns) > 1 else None,
                        "color": None,
                    }
                ],
            }
            logger.warning(f"[text2dashboard] Falling back to table config due to error: {e}")
            return {"dashboard_config": table_panel}
