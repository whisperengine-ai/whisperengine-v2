# Multi-Bot Deployment Guide

## 🎯 Overview

WhisperEngine v2 now uses a **unified Docker Compose setup** with profiles for cleaner multi-bot management.

### What Changed?

**Old Way (6 separate files):**
```bash
# Had to manage separate compose files
docker-compose -f docker-compose.v2.yml up -d          # Infrastructure
docker-compose -f docker-compose.elena.yml up -d       # Elena
docker-compose -f docker-compose.ryan.yml up -d        # Ryan
# ... etc. Lots of "orphan container" warnings
```

**New Way (1 unified file):**
```bash
# Simple, profile-based deployment
./bot.sh infra            # Just infrastructure
./bot.sh up elena         # Infra + Elena
./bot.sh up all           # Everything
docker compose --profile elena --profile ryan up -d  # Custom combo
```

## 🚀 Quick Start

### 1. Migrate from Old Setup

```bash
./scripts/migrate-to-unified.sh
```

This interactive script will:
- Stop old containers cleanly
- Start unified infrastructure
- Let you choose which bots to deploy

### 2. Common Operations

```bash
# Start infrastructure only
./bot.sh infra

# Start all bots
./bot.sh up all

# Start specific bot
./bot.sh up elena
./bot.sh up dream

# View status
./bot.sh ps

# Watch logs
./bot.sh logs all      # All containers
./bot.sh logs elena    # Just Elena

# Restart a bot (after code changes)
./bot.sh restart elena

# Stop everything
./bot.sh down

# Rebuild images
./bot.sh build
```

## 📋 Available Commands

Run `make help` to see all options:

```
WhisperEngine v2 - Multi-Bot Management

Targets:
  infra                Start only infrastructure
  up-all               Start infrastructure + all bots
  up-elena             Start infrastructure + elena
  up-ryan              Start infrastructure + ryan
  up-dotty             Start infrastructure + dotty
  up-aria              Start infrastructure + aria
  up-dream             Start infrastructure + dream
  down                 Stop and remove all containers
  down-volumes         Stop all containers and remove volumes
  logs                 Tail logs from all containers
  logs-elena           Tail logs from elena
  restart-elena        Restart elena bot
  ps                   Show status of all containers
  clean                Remove stopped containers
  shell-elena          Open shell in elena container
  shell-postgres       Open psql shell
  shell-neo4j          Open cypher-shell
```

## 🏗️ Architecture

### Profile-Based Deployment

The unified compose file uses **Docker Compose profiles**:

```yaml
services:
  # Infrastructure (always available)
  postgres: {...}
  qdrant: {...}
  neo4j: {...}
  influxdb: {...}

  # Bots (profile-gated)
  elena:
    profiles: ["elena", "all"]
    ...
  
  ryan:
    profiles: ["ryan", "all"]
    ...
```

### Benefits

1. **Single Network**: All services on `v2_network`, no more external network references
2. **Proper Dependencies**: `depends_on` with health checks ensures infrastructure is ready
3. **No Orphan Warnings**: All services defined in one file
4. **Selective Deployment**: Start only what you need
5. **Cleaner Management**: One command to rule them all

## 🔧 Advanced Usage

### Start Multiple Specific Bots

```bash
docker compose \
  --profile elena \
  --profile dream \
  up -d --build
```

### Infrastructure Only (for local development)

```bash
./bot.sh infra
# Then run bots with: python run_v2.py elena
```

### Production Deployment

```bash
# Start all bots with auto-restart
./bot.sh up all

# Verify health
./bot.sh ps

# Monitor logs
./bot.sh logs all
```

### Updating Code

```bash
# Option 1: Restart specific bot (fast, no rebuild)
./bot.sh restart elena

# Option 2: Rebuild and restart (after dependency changes)
./bot.sh up elena
```

### Database Access

```bash
# PostgreSQL
docker exec -it whisperengine-v2-postgres psql -U whisper -d whisperengine_v2

# Neo4j
docker exec -it whisperengine-v2-neo4j cypher-shell -u neo4j -p password

# Qdrant (HTTP API)
curl http://localhost:6333/collections

# InfluxDB (Web UI)
open http://localhost:8086
```

## 🗂️ File Structure

```
whisperengine-v2/
├── docker-compose.yml            # Single unified compose file
├── bot.sh                        # Management script
├── scripts/
│   └── migrate-to-unified.sh    # Migration helper
└── .env.*                        # Per-bot config
```

## 🔄 Migration Notes

### Old Compose Files

The old per-bot compose files have been removed. The unified `docker-compose.yml` is now the single source of truth.

### Volumes & Data

All data volumes remain unchanged:
- `postgres_data_v2`
- `qdrant_data_v2`
- `neo4j_data_v2`
- `influxdb_data_v2`

Your existing data is safe!

### Environment Files

No changes needed to `.env.{bot}` files. They work the same way.

## 🐛 Troubleshooting

### "network not found" error

```bash
# Clean up old networks
docker network prune -f

# Restart with unified compose
make down
make up-all
```

### Bot won't start

```bash
# Check infrastructure health
./bot.sh ps

# Ensure postgres and neo4j are healthy before starting bots
docker compose up -d
# Wait for health checks...
docker compose --profile elena up -d
```

### Orphan container warnings

If you still see these, you're mixing old and new compose files. Stop old setup first:

```bash
docker compose -f docker-compose.v2.yml down
docker compose -f docker-compose.elena.yml down
# ... stop all old files

# Then use unified only
./bot.sh up all
```

## 📊 Resource Management

### Memory Footprint

- **Infrastructure only**: ~2GB RAM
- **+ 1 bot**: ~2.5GB RAM
- **+ All 5 bots**: ~4-5GB RAM

### Selective Deployment Strategy

For development machines with limited resources:

```bash
# Infrastructure + 1 bot for testing
./bot.sh infra
./bot.sh up elena

# Production: All bots
./bot.sh up all
```

## 🎓 Best Practices

1. **Always start infrastructure first** (or use `./bot.sh up {bot}` which handles it)
2. **Use `./bot.sh ps`** to verify health before assuming failure
3. **Check logs** with `./bot.sh logs {bot}` when debugging
4. **Restart > Rebuild** when only code changes (faster)
5. **Clean up** periodically with `docker system prune -f`

## 📚 Next Steps

- See `./bot.sh help` for full command reference
- Run `./scripts/migrate-to-unified.sh` for guided migration
- Check `docker-compose.yml` for infrastructure details
