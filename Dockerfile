# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies separately to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY augment_mcp ./augment_mcp

# Default host binding and port 
ENV AUGMENT_MCP_HOST=0.0.0.0 \
    AUGMENT_MCP_PORT=8000

EXPOSE 8000

ENTRYPOINT ["python3", "-m", "augment_mcp.server"]
