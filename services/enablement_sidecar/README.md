# Enablement Sidecar Service

Standalone FastAPI service for enablement job submission and monitoring.
Designed for sidecar deployment alongside robotics platforms.

## Usage

```bash
# Install TensorGuard
pip install -e ../../

# Run sidecar
uvicorn services.enablement_sidecar.main:app --port 8001
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TG_SIDECAR_RUNS_DIR` | Directory for job runs | `./runs` |
| `TG_SIDECAR_DP_BUDGET` | Differential privacy budget | `100.0` |

## Endpoints

- `POST /jobs` - Submit a new job
- `GET /jobs/{run_id}` - Get job status
- `GET /health` - Health check
- `GET /ready` - Readiness check

## Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8001
CMD ["uvicorn", "services.enablement_sidecar.main:app", "--host", "0.0.0.0", "--port", "8001"]
```
