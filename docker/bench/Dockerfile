# docker/bench/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y make curl build-essential

# Install dependencies
COPY pyproject.toml README.md requirements-bench.lock requirements.lock /app/
RUN pip install --no-cache-dir -r requirements-bench.lock

# Copy Source
COPY . .
RUN pip install --no-cache-dir --no-deps .[bench]

# Set Env
ENV PYTHONPATH=/app/src

# Default Command
CMD ["make", "bench"]
