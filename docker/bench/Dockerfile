# docker/bench/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y make curl build-essential

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install psutil matplotlib

# Copy Source
COPY . .
RUN pip install -e .

# Set Env
ENV PYTHONPATH=/app/src

# Default Command
CMD ["make", "bench"]
