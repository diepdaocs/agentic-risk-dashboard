#!/bin/bash
# Script to run both FastAPI and Streamlit locally
python -m src.api.app &
sleep 3
streamlit run src/frontend/app.py --server.port 8501 --server.address 0.0.0.0 &
