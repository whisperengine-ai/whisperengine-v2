# WhisperEngine v2 - Quick Reference

**Version:** 2.5 | **Architecture:** E17 Supergraph | **Updated:** December 2025

## 🎯 Most Common Commands

```bash
# Start everything
./bot.sh up all

# Start infrastructure + specific bot
./bot.sh up elena

# Check status
./bot.sh ps

# View logs
./bot.sh logs elena

# Restart after code changes
./bot.sh restart elena

# Stop everything
./bot.sh down

# Ingest Character Backgrounds (New)
DISCORD_BOT_NAME=elena python scripts/ingest_character_facts.py
```

## 🚀 Deployment Patterns

### Pattern 1: Development (Primary - Docker)
```bash
./bot.sh up elena       # Start bot in Docker
./bot.sh logs elena -f  # Monitor logs
./bot.sh restart elena  # After code changes
```

### Pattern 2: Development (Local Python - Debugging Only)
```bash
./bot.sh infra up           # Infrastructure only
source .venv/bin/activate
python run_v2.py elena      # For debugger breakpoints
```

### Pattern 3: Production (All Bots)
```bash
./bot.sh up all
./bot.sh logs all  # Monitor
```

### Pattern 4: Selective Deployment
```bash
./bot.sh up elena
./bot.sh up dream
# Or use docker compose directly:
docker compose --profile elena --profile dream up -d --build

# Scale workers (Default is 3)
docker compose --profile worker up -d --scale worker=5
```

## 📊 Status Check
```bash
./bot.sh ps
# Shows: name, status, ports for all containers
```

## 🔍 Debugging

```bash
# View logs
./bot.sh logs elena      # Specific bot
./bot.sh logs worker     # Background worker
./bot.sh logs all        # All containers

# Shell access
docker exec -it whisperengine-v2-elena /bin/bash       # Bot container
docker exec -it whisperengine-v2-worker-1 /bin/bash    # Worker container (1st instance)
docker exec -it whisperengine-v2-postgres psql -U whisper -d whisperengine_v2  # Database
docker exec -it whisperengine-v2-neo4j cypher-shell -u neo4j -p password       # Neo4j

# Check health
docker inspect whisperengine-v2-elena | jq '.[0].State.Health'
```

## 🔄 Common Workflows

### Deploy New Code
```bash
# Fast restart (code-only changes)
./bot.sh restart elena

# Full rebuild (dependency changes)
./bot.sh up elena
```

### Add New Bot
1. Create `.env.{newbot}`
2. Add character files in `characters/{newbot}/`
3. Add to `docker-compose.yml`:
```yaml
newbot:
  profiles: ["newbot", "all"]
  image: whisperengine-v2:latest
  build:
    context: .
    dockerfile: Dockerfile
  container_name: whisperengine-v2-newbot
  restart: unless-stopped
  volumes:
    - .:/app
    - /app/.venv
    - ./logs:/app/logs
  env_file:
    - .env.newbot
  environment:
    - DISCORD_BOT_NAME=newbot
  ports:
    - "8005:8005"  # Choose unique port
  depends_on:
    postgres:
      condition: service_healthy
    neo4j:
      condition: service_healthy
    qdrant:
      condition: service_started
    influxdb:
      condition: service_started
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8005/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s
  networks:
    - v2_network
```
4. Add Makefile targets:
```makefile
up-newbot:
	docker compose -f $(COMPOSE_FILE) --profile newbot up -d --build

logs-newbot:
	docker logs -f whisperengine-v2-newbot

restart-newbot:
	docker compose -f $(COMPOSE_FILE) restart newbot
```

### Cleanup
```bash
# Stop all containers
./bot.sh down

# Remove stopped containers
docker system prune -f

# Nuclear option (removes data!)
docker compose --profile all down -v
```

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| "network not found" | `docker network prune -f && ./bot.sh down && ./bot.sh up all` |
| Bot won't start | Check `./bot.sh ps` for infrastructure health first |
| Orphan warnings | Stop all old compose files, use unified only |
| Out of memory | Start fewer bots: `./bot.sh up elena` instead of `./bot.sh up all` |
| Neo4j restart loop | Already fixed in compose (HTTP healthcheck) |
| InfluxDB 401 errors | Already fixed in code (org parameter added) |

## 📝 File Locations

```
Project Root
├── docker-compose.yml            ← Main compose file
├── bot.sh                        ← Management script
├── .env.{bot}                    ← Per-bot configuration
├── characters/{bot}/             ← Character definitions
│   ├── character.md
│   └── goals.yaml
└── docs/
    └── MULTI_BOT_DEPLOYMENT.md   ← Full guide
```

## 🎓 Best Practices

1. ✅ Use `./bot.sh` for common operations (simpler than docker compose)
2. ✅ Check `./bot.sh ps` before assuming failure
3. ✅ Use `restart` for code changes (faster than rebuild)
4. ✅ Monitor logs with `./bot.sh logs {bot}`
5. ✅ Keep infrastructure running, restart bots as needed
6. ❌ Don't mix old compose files with new unified setup
7. ✅ Use docker compose directly when you need custom flags

## 🔗 Port Reference

### Bot Ports
| Bot | Port | Role | Model |
|-----|------|------|-------|
| elena | 8000 | **Dev Primary** | Claude Sonnet 4.5 |
| ryan | 8001 | Test | Llama 3.3 70B |
| dotty | 8002 | Personal | Claude 3.7 Sonnet |
| aria | 8003 | Test | Gemini 2.0 Flash |
| dream | 8004 | Test | DeepSeek Chat |
| jake | 8005 | Test | GPT-4o Mini |
| sophia | 8006 | Test | Gemini 2.5 Pro |
| marcus | 8007 | Test | Mistral Large |
| nottaylor | 8008 | **Production** | GPT-4o |
| gabriel | 8009 | Personal | Mistral Medium 3.1 |
| aetheris | 8011 | Personal | Claude Sonnet 4 |

### Infrastructure Ports
| Service | Port | URL |
|---------|------|-----|
| PostgreSQL | 5432 | psql -h localhost -U whisper -d whisperengine_v2 |
| Qdrant | 6333 | http://localhost:6333/dashboard |
| Neo4j Browser | 7474 | http://localhost:7474 |
| Neo4j Bolt | 7687 | bolt://localhost:7687 |
| InfluxDB | 8086 | http://localhost:8086 |
| Redis | 6379 | redis-cli -h localhost |

## 🆘 Getting Help

```bash
# See all available commands
./bot.sh help

# Read full deployment guide
cat docs/MULTI_BOT_DEPLOYMENT.md

# Check container logs
./bot.sh logs {bot}

# Inspect container
docker inspect whisperengine-v2-{bot}
```

## 📚 Key Documentation

| Document | Purpose |
|----------|--------|
| [Graph Systems Design](docs/architecture/GRAPH_SYSTEMS_DESIGN.md) | Unified graph architecture (Data, Orchestration, Conceptual) |
| [Agent Graph System](docs/architecture/AGENT_GRAPH_SYSTEM.md) | LangGraph Supergraph implementation |
| [Message Flow](docs/architecture/MESSAGE_FLOW.md) | Complete request lifecycle |
| [API Reference](docs/API_REFERENCE.md) | REST API endpoints |
| [copilot-instructions](.github/copilot-instructions.md) | AI agent development guide |
