FROM python:3.9-slim

WORKDIR /app

# Install system dependencies (needed for some crypto libs)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy Core SDK and Platform
COPY src /app/src
COPY requirements.txt /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install "uvicorn[standard]" "fastapi" "sqlmodel" "python-jose[cryptography]" "passlib[argon2]" "python-multipart"

# Env
ENV PYTHONPATH=/app/src
ENV DATABASE_URL="postgresql://user:pass@db:5432/tensorguard"

# Run
CMD ["uvicorn", "tensorguard.platform.main:app", "--host", "0.0.0.0", "--port", "8000"]
