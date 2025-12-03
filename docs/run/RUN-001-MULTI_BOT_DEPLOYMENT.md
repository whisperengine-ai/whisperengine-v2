# Multi-Bot Deployment Guide

## 🎯 Overview

WhisperEngine v2 uses a **unified Docker Compose setup** with profiles for multi-bot management. All 9 character bots share the same infrastructure (PostgreSQL, Qdrant, Neo4j, InfluxDB) while running as isolated containers.

### Available Bots

| Bot | Port | Description |
|-----|------|-------------|
| elena | 8000 | Marine biologist from La Jolla |
| ryan | 8001 | - |
| dotty | 8002 | - |
| aria | 8003 | AI agent on ISV Meridian |
| dream | 8004 | - |
| jake | 8005 | - |
| sophia | 8006 | - |
| marcus | 8007 | AI Research Scientist |
| nottaylor | 8008 | - |

## 🚀 Quick Start

### Common Operations

```bash
# Start infrastructure only (databases)
./bot.sh infra up

# Start infrastructure + specific bot
./bot.sh up elena
./bot.sh up dream

# Start all bots
./bot.sh up all

# View status
./bot.sh ps

# Watch logs
./bot.sh logs all      # All containers
./bot.sh logs elena    # Just Elena

# Restart a bot (after code changes)
./bot.sh restart elena

# Stop a specific bot
./bot.sh stop elena

# Stop and remove a bot
./bot.sh down elena

# Stop everything
./bot.sh down all

# Rebuild images
./bot.sh build
```

## 📋 Available Commands

Run `./bot.sh help` to see all options:

```
WhisperEngine v2 - Bot Management

Usage: ./bot.sh [command]

Commands:
  infra [up|down]       Start or stop infrastructure services
  up [bot|all]          Start infrastructure + bot(s) (builds images)
  down [bot|all]        Stop and remove containers
  start [bot|all]       Start existing containers (no build)
  stop [bot|all]        Stop running containers
  restart [bot|all]     Restart containers
  logs [bot|all]        Show logs
  ps                    Show status of all containers
  build                 Rebuild bot images

Examples:
  ./bot.sh infra up     # Start just databases
  ./bot.sh up elena     # Start infrastructure + Elena
  ./bot.sh up all       # Start everything
  ./bot.sh stop elena   # Stop Elena
  ./bot.sh start elena  # Start Elena
  ./bot.sh logs elena   # Watch Elena's logs
  ./bot.sh restart elena # Restart Elena
```

## 🏗️ Architecture

### Profile-Based Deployment

The unified compose file uses **Docker Compose profiles**:

```yaml
services:
  # Infrastructure (always available, no profile)
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
  
  # ... 9 bots total
```

### Benefits

1. **Single Network**: All services on `v2_network`
2. **Proper Dependencies**: `depends_on` with health checks ensures infrastructure is ready
3. **Selective Deployment**: Start only what you need
4. **Isolated Containers**: Each bot runs independently

## 🔧 Advanced Usage

### Start Multiple Specific Bots

```bash
docker compose \
  --profile elena \
  --profile dream \
  --profile aria \
  up -d --build
```

### Infrastructure Only (for local Python debugging)

Only use this when you need debugger breakpoints:

```bash
./bot.sh infra up
# Then run bot directly with Python:
source .venv/bin/activate
python run_v2.py elena
```

> **Note:** Docker is the primary way to run bots, even in development. Use `./bot.sh up elena` instead for normal development.

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

# Neo4j (Cypher shell)
docker exec -it whisperengine-v2-neo4j cypher-shell -u neo4j -p password

# Neo4j (Web UI)
open http://localhost:7474

# Qdrant (HTTP API)
curl http://localhost:6333/collections

# InfluxDB (Web UI)
open http://localhost:8086
```

## 🗂️ File Structure

```
whisperengine-v2/
├── docker-compose.yml       # Unified compose file (infra + all bots)
├── bot.sh                   # Management script
├── run_v2.py                # Local bot runner
├── .env.example             # Template for bot config
├── .env.elena               # Elena's config
├── .env.ryan                # Ryan's config
├── ...                      # Other bot configs
└── characters/
    ├── elena/               # Elena's character files
    ├── ryan/                # Ryan's character files
    └── ...                  # Other characters
```

## 🔄 Adding a New Bot

See [Creating New Characters](CREATING_NEW_CHARACTERS.md) for the complete guide. Quick summary:

1. Create character directory: `mkdir characters/newbot`
2. Add character files: `character.md`, `goals.yaml`
3. Create environment file: `.env.newbot`
4. Add service to `docker-compose.yml` with unique port
5. Deploy: `./bot.sh up newbot`

## 🐛 Troubleshooting

### "network not found" error

```bash
# Clean up old networks
docker network prune -f

# Restart infrastructure
./bot.sh down all
./bot.sh up all
```

### Bot won't start

```bash
# Check infrastructure health first
./bot.sh ps

# Start infrastructure and wait for health checks
./bot.sh infra up
# Wait 30-60 seconds for all services to be healthy
./bot.sh up elena
```

### Container keeps restarting

```bash
# Check logs for errors
./bot.sh logs elena

# Common issues:
# - Missing .env.elena file
# - Invalid Discord token
# - Database connection refused (infra not ready)
```

### "Character not found" error

1. Ensure `characters/{botname}/character.md` exists
2. Verify `DISCORD_BOT_NAME` in `.env.{botname}` matches directory name

## 📊 Resource Management

### Memory Footprint

| Configuration | RAM Usage |
|--------------|-----------|
| Infrastructure only | ~2GB |
| + 1 bot | ~2.5GB |
| + All 9 bots | ~6-7GB |

### Selective Deployment Strategy

For development machines with limited resources:

```bash
# Infrastructure + 1 bot for testing
./bot.sh infra up
./bot.sh up elena

# Production: All bots
./bot.sh up all
```

### Port Allocation

Each bot exposes a unique API port:

| Bot | Port |
|-----|------|
| elena | 8000 |
| ryan | 8001 |
| dotty | 8002 |
| aria | 8003 |
| dream | 8004 |
| jake | 8005 |
| sophia | 8006 |
| marcus | 8007 |
| nottaylor | 8008 |

## 🎓 Best Practices

1. **Always start infrastructure first**: Use `./bot.sh infra up` or `./bot.sh up {bot}` (which handles it automatically)
2. **Check health before debugging**: Run `./bot.sh ps` to see container status
3. **Use logs for debugging**: `./bot.sh logs {bot}` shows real-time output
4. **Restart vs Rebuild**: Use `restart` for code changes, `up` for dependency changes
5. **Clean up periodically**: Run `docker system prune -f` to free disk space
6. **Local development**: Run infrastructure in Docker, bot with Python for faster iteration

## 📚 Related Documentation

- [Creating New Characters](CREATING_NEW_CHARACTERS.md) - Step-by-step guide to adding bots
- [Cognitive Engine](architecture/COGNITIVE_ENGINE.md) - How the AI works
- [Memory System](architecture/MEMORY_SYSTEM_V2.md) - Vector and graph memory
- [Infrastructure & Deployment](architecture/INFRASTRUCTURE_DEPLOYMENT.md) - Container architecture
