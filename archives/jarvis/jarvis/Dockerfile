FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

# Install system dependencies (curl for health checks, git for sync test)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Create database and logs directories if not exists
RUN mkdir -p /app/db /app/cache /app/models /app/logs

# Set Entrypoint to launch the interactive CLI
ENTRYPOINT ["python", "main.py"]
