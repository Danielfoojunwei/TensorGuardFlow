# TensorGuardFlow Installation Guide

**Version:** 2.3.0
**Edition:** Self-Hosted (Single Machine)

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Disk | 20 GB | 50 GB SSD |
| Network | 100 Mbps | 1 Gbps |

### Software Requirements

- **Docker Desktop** (Windows/macOS) or **Docker Engine** (Linux)
  - Version 24.0 or higher
  - Docker Compose V2
- **Git** (optional, for cloning repository)

### Supported Platforms

- Windows 11 x64
- macOS 14+ (Apple Silicon or Intel)
- Ubuntu 22.04 LTS or newer

---

## Installation Steps

### Step 1: Obtain TensorGuardFlow

**Option A: Clone from repository**
```bash
git clone https://github.com/tensorguard/tensorguardflow.git
cd tensorguardflow
```

**Option B: Download release archive**
```bash
# Extract the release archive
unzip tensorguardflow-2.3.0.zip
cd tensorguardflow-2.3.0
```

### Step 2: Configure Environment (Optional)

Create a `.env` file for custom configuration:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Required for production
TG_SECRET_KEY=your-secret-key-here-min-32-chars

# Optional: Database (defaults to SQLite)
# DATABASE_URL=postgresql://user:pass@localhost/tensorguard

# Optional: Environment
TG_ENVIRONMENT=production
```

### Step 3: Start TensorGuardFlow

**Development Mode (SQLite)**
```bash
docker compose up -d
```

**Production Mode (PostgreSQL)**
```bash
docker compose --profile production up -d
```

### Step 4: Verify Installation

Check that services are running:
```bash
docker compose ps
```

Expected output:
```
NAME                    STATUS
tensorguard-api         running (healthy)
tensorguard-worker      running
```

Check the health endpoint:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy", "version": "2.3.0"}
```

### Step 5: Access the Application

Open your browser and navigate to:
```
http://localhost:8000
```

---

## Initial Setup

### Create Your Organization

1. Navigate to `http://localhost:8000`
2. Click "Get Started" or visit `/onboard`
3. Enter:
   - Organization name
   - Admin email address
   - Strong password (min 12 characters)
4. Click "Create Organization"
5. **Important:** Save the credentials securely

### Create Your First Fleet

1. Login with your admin credentials
2. Navigate to "Fleets" in the sidebar
3. Click "Create Fleet"
4. Enter a fleet name (e.g., "Production Devices")
5. **Important:** Copy and save the API key immediately
   - The API key is only shown once
   - Store it securely for device configuration

---

## Start/Stop Commands

### Start all services
```bash
docker compose up -d
```

### Stop all services (preserves data)
```bash
docker compose down
```

### Stop and remove all data
```bash
docker compose down -v
```

### View logs
```bash
docker compose logs -f
```

### Restart services
```bash
docker compose restart
```

---

## Troubleshooting

### Container won't start

1. Check Docker is running:
   ```bash
   docker info
   ```

2. Check for port conflicts:
   ```bash
   netstat -an | grep 8000
   ```

3. View container logs:
   ```bash
   docker compose logs api
   ```

### Health check failing

1. Wait 30 seconds for startup to complete
2. Check database connectivity:
   ```bash
   docker compose logs api | grep -i database
   ```

3. Verify environment variables:
   ```bash
   docker compose config
   ```

### Cannot access UI

1. Verify port binding:
   ```bash
   docker compose ps
   ```

2. Check firewall settings
3. Try accessing from localhost only first

### Database issues

For SQLite:
```bash
# Reset database (WARNING: deletes all data)
docker compose down -v
docker compose up -d
```

For PostgreSQL:
```bash
# Check database logs
docker compose logs db
```

---

## Upgrade Instructions

### Backup First
```bash
# For SQLite
cp tg_platform.db tg_platform.db.backup

# For PostgreSQL
docker compose exec db pg_dump -U tensorguard tensorguard > backup.sql
```

### Upgrade
```bash
# Pull latest version
git pull origin main

# Rebuild containers
docker compose down
docker compose up -d --build

# Run migrations
docker compose exec api python -m alembic upgrade head
```

---

## Uninstallation

### Complete removal
```bash
# Stop and remove containers, networks, volumes
docker compose down -v --remove-orphans

# Remove images
docker rmi $(docker images | grep tensorguard | awk '{print $3}')

# Remove project directory
cd ..
rm -rf tensorguardflow
```

---

## Support

For technical support:
1. Collect diagnostics: `./scripts/qa/collect_diagnostics.sh`
2. Send the generated zip file to support
3. Email: support@tensorguard.dev

---

## Security Notices

- Change the default `TG_SECRET_KEY` before production use
- Use HTTPS in production (configure reverse proxy)
- Regularly rotate fleet API keys
- Keep Docker and the OS updated
- Review the [Security Guide](./SECURITY.md) for best practices
