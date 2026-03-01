import streamlit as st
import requests
import pandas as pd
import json
import os

API_URL = os.environ.get("API_URL", "http://localhost:8000/query")

st.set_page_config(page_title="Agentic Risk Dashboard", layout="wide")

st.title("Agentic Risk Dashboard")
st.markdown("Use natural language to query trading and risk data and generate dynamic dashboards.")

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")
    st.markdown("LLM Settings and Database parameters are configured in the backend (FastAPI).")
    st.markdown("**Example Queries:**")
    st.markdown("- *Show me the top 5 trades by notional value.*")
    st.markdown("- *What is the total PnL by desk for the last week?*")
    st.markdown("- *Show me the DV01 exposure by instrument for the Rates desk.*")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # Display dashboard if exists in the message context
        if "dashboard_config" in message and message["dashboard_config"]:
            st.json(message["dashboard_config"], expanded=False)

            # Basic rendering logic for Streamlit
            config = message["dashboard_config"]
            data = message.get("data", [])
            if data:
                df = pd.DataFrame(data)
                st.subheader(config.get("title", "Dashboard View"))

                panels = config.get("panels", [])

                # Create columns based on number of panels
                cols = st.columns(max(1, len(panels)))

                for i, panel in enumerate(panels):
                    with cols[i]:
                        st.markdown(f"**{panel.get('title', 'Chart')}**")
                        chart_type = panel.get("type", "table")
                        x_col = panel.get("x_axis")
                        y_col = panel.get("y_axis")
                        color_col = panel.get("color")

                        try:
                            if chart_type == "bar":
                                if x_col and y_col:
                                    st.bar_chart(df, x=x_col, y=y_col, color=color_col)
                                else:
                                    st.bar_chart(df)
                            elif chart_type == "line":
                                if x_col and y_col:
                                    st.line_chart(df, x=x_col, y=y_col, color=color_col)
                                else:
                                    st.line_chart(df)
                            elif chart_type == "scatter":
                                if x_col and y_col:
                                    st.scatter_chart(df, x=x_col, y=y_col, color=color_col)
                                else:
                                    st.scatter_chart(df)
                            else: # Default to table
                                st.dataframe(df)
                        except Exception as e:
                            st.error(f"Error rendering {chart_type} chart: {e}")
                            st.dataframe(df)

# React to user input
if prompt := st.chat_input("Ask a question about your risk or trades..."):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)

    with st.spinner("Agents are analyzing your request..."):
        try:
            response = requests.post(API_URL, json={"query": prompt})
            response_data = response.json()

            error = response_data.get("error")
            sql_query = response_data.get("sql_query")
            dashboard_config = response_data.get("dashboard_config")
            data = response_data.get("data", [])

            # Construct AI message
            ai_message_content = "Here is the result of your query."
            if error:
                ai_message_content = f"**Error:** {error}"
            elif sql_query:
                ai_message_content = f"**Generated SQL:**\n```sql\n{sql_query}\n```"
                if len(data) > 0:
                    ai_message_content += f"\n\nFound {len(data)} rows."
                else:
                    ai_message_content += "\n\nNo data found."

            # Add AI response to UI
            with st.chat_message("assistant"):
                st.markdown(ai_message_content)

                if not error and dashboard_config:
                    st.json(dashboard_config, expanded=False)
                    df = pd.DataFrame(data)
                    st.subheader(dashboard_config.get("title", "Dashboard View"))

                    panels = dashboard_config.get("panels", [])
                    cols = st.columns(max(1, len(panels)))

                    for i, panel in enumerate(panels):
                        with cols[i]:
                            st.markdown(f"**{panel.get('title', 'Chart')}**")
                            chart_type = panel.get("type", "table")
                            x_col = panel.get("x_axis")
                            y_col = panel.get("y_axis")
                            color_col = panel.get("color")

                            try:
                                if chart_type == "bar":
                                    if x_col and y_col:
                                        st.bar_chart(df, x=x_col, y=y_col, color=color_col)
                                    else:
                                        st.bar_chart(df)
                                elif chart_type == "line":
                                    if x_col and y_col:
                                        st.line_chart(df, x=x_col, y=y_col, color=color_col)
                                    else:
                                        st.line_chart(df)
                                elif chart_type == "scatter":
                                    if x_col and y_col:
                                        st.scatter_chart(df, x=x_col, y=y_col, color=color_col)
                                    else:
                                        st.scatter_chart(df)
                                else: # Default to table
                                    st.dataframe(df)
                            except Exception as e:
                                st.error(f"Error rendering {chart_type} chart: {e}")
                                st.dataframe(df)

            # Add user and ai message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.messages.append({
                "role": "assistant",
                "content": ai_message_content,
                "dashboard_config": dashboard_config,
                "data": data
            })

        except requests.exceptions.ConnectionError:
            st.error("Failed to connect to the backend API. Please make sure the FastAPI server is running.")
