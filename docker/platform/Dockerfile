FROM python:3.9-slim

WORKDIR /app

# Install system dependencies (needed for some crypto libs)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy Core SDK and Platform
COPY pyproject.toml README.md /app/
COPY requirements.lock /app/
COPY src /app/src

# Install dependencies (pinned) and package
RUN pip install --no-cache-dir -r requirements.lock
RUN pip install --no-cache-dir --no-deps .

# Env
ENV PYTHONPATH=/app/src
ENV DATABASE_URL="postgresql://user:pass@db:5432/tensorguard"

# Run
CMD ["uvicorn", "tensorguard.platform.main:app", "--host", "0.0.0.0", "--port", "8000"]
