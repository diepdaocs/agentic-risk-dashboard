FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (build essentials, SQLite, etc)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Ensure PYTHONPATH includes the /app directory
ENV PYTHONPATH=/app

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "src.api.app"]
