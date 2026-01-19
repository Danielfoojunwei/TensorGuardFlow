# TensorGuardFlow Local Development Quickstart

This guide gets you from zero to a working local development environment in under 5 minutes.

## Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend)
- Git

## Quick Start (Backend Only)

```bash
# 1. Clone and enter repo
git clone https://github.com/Danielfoojunwei/TensorGuardFlow
cd TensorGuardFlow

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
make install
# Or manually: pip install -e ".[all]"

# 4. Initialize database
make db-init

# 5. Start development server
make dev
```

The backend will be available at:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Quick Start (Full Stack with Frontend)

```bash
# After completing backend setup above...

# 6. Build frontend (one-time)
cd frontend
npm install
npm run build
cd ..

# 7. Restart backend (will now serve frontend)
make dev
```

The dashboard will be available at http://localhost:8000

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TG_ENVIRONMENT` | `development` | Set to `production` for production mode |
| `TG_SECRET_KEY` | Auto-generated | JWT signing key (REQUIRED in production) |
| `TG_DEMO_MODE` | `false` | Enable demo mode (skips auth, NEVER in production) |
| `DATABASE_URL` | `sqlite:///./tg_platform.db` | Database connection string |
| `TG_LOG_LEVEL` | `INFO` | Logging level |

## First-Time Setup (Create Admin User)

After starting the server, create your first admin user:

```bash
# Using curl
curl -X POST "http://localhost:8000/api/v1/onboarding/init?name=MyOrg&admin_email=admin@example.com&admin_pass=SecurePassword123!"

# Response contains tenant info
```

## Login and Get Token

```bash
# Login
curl -X POST "http://localhost:8000/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin@example.com", "password": "SecurePassword123!"}'

# Response: {"access_token": "eyJ...", "token_type": "bearer"}
```

## Create a Fleet and Get API Key

```bash
# Create fleet (use token from login)
curl -X POST "http://localhost:8000/api/v1/fleets?name=my-fleet" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

# Response includes one-time API key:
# {"id": "...", "name": "my-fleet", "api_key": "tg_abc123...", "instruction": "Save this key!"}
```

## Send Telemetry from Agent

```bash
# Using Fleet Bearer auth
curl -X POST "http://localhost:8000/api/v1/telemetry/ingest" \
  -H "Content-Type: application/json" \
  -H "Authorization: Fleet tg_YOUR_FLEET_KEY" \
  -d '{
    "batch_id": "batch-001",
    "device_info": {"device_id": "robot-001"},
    "messages": [{
      "topic": "telemetry.stage",
      "timestamp_ns": 1705600000000000000,
      "payload": {"stage": "capture", "status": "ok", "latency_ms": 12.5}
    }]
  }'
```

## Available Make Commands

```
make help          # Show all commands
make dev           # Start development server
make dev-backend   # Start backend only
make dev-frontend  # Start frontend dev server
make test          # Run all tests
make lint          # Run linter
make db-init       # Initialize database
make clean         # Clean temporary files
```

## Troubleshooting

### Backend won't start
- Check Python version: `python --version` (need 3.10+)
- Ensure dependencies installed: `pip install -e ".[all]"`
- Check port 8000 is free: `lsof -i :8000`

### Database errors
- Delete old database: `rm tg_platform.db`
- Re-initialize: `make db-init`

### Frontend not loading
- Ensure frontend is built: `cd frontend && npm run build`
- Or run frontend dev server separately: `make dev-frontend`

### API returns 401 Unauthorized
- Ensure you're passing the auth token: `Authorization: Bearer YOUR_TOKEN`
- Token may have expired (30 min default) - login again

## Next Steps

1. Read the [API Documentation](http://localhost:8000/docs)
2. Explore the [Dashboard UI](http://localhost:8000)
3. Connect an [Agent](./AGENT_SETUP.md)
