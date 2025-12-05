# WhisperEngine v2 - Backup & Restore Guide

## Overview

WhisperEngine v2 includes comprehensive backup/restore scripts for all databases:
- **PostgreSQL** - Chat history, users, trust scores, sessions
- **Qdrant** - Vector embeddings for semantic memory
- **Neo4j** - Knowledge graph of entities and relationships  
- **InfluxDB** - Metrics and analytics data

## Quick Start

### Manual Backup

```bash
# Run backup script
./scripts/backup.sh

# Output: backups/20251205_135600/
#   ├── postgres.dump          (Chat history, relationships, etc.)
#   ├── qdrant_snapshot.tar    (Vector memory)
#   ├── neo4j.cypher           (Knowledge graph)
#   └── influxdb/              (Metrics)
```

### Manual Restore

```bash
# List available backups
ls -la backups/

# Restore from specific backup
./scripts/restore.sh ./backups/20251205_135600

# ⚠️  You'll be asked to confirm before overwriting data
# After restore, restart bots:
./bot.sh restart all
```

---

## Automated Daily Backups

Add to your crontab to run backups every day at 2 AM:

```bash
crontab -e

# Add this line:
0 2 * * * cd /path/to/whisperengine-v2 && ./scripts/backup.sh >> backups/cron.log 2>&1
```

To verify it's set up:
```bash
crontab -l | grep backup.sh
```

---

## Backup Storage

**Default location**: `./backups/`

**To use custom location**:
```bash
# Single backup
BACKUP_DIR=/mnt/backups ./scripts/backup.sh

# Or set environment variable
export BACKUP_DIR=/mnt/backups
./scripts/backup.sh
```

---

## Disaster Recovery Scenarios

### Scenario 1: Database Corruption (What We Just Recovered From)

```bash
# 1. Create fresh backup as safety net
./scripts/backup.sh

# 2. Stop all containers
./bot.sh stop all

# 3. Restore from last good backup
./scripts/restore.sh ./backups/20251205_120000

# 4. Restart all containers
./bot.sh up all -d

# 5. Verify health
curl http://localhost:8000/health
```

### Scenario 2: Restore Specific Database Only

Currently all-or-nothing, but you can modify scripts for partial restore:

```bash
# Edit restore.sh to only restore PostgreSQL
# Remove the Qdrant/Neo4j/InfluxDB sections
# Then run: ./scripts/restore.sh ./backups/20251205_120000
```

### Scenario 3: Point-in-Time Recovery

Backups are timestamped. Keep multiple backups:
```bash
# Backups from different times
ls -lh backups/

backups/20251205_020000/  # 2 AM yesterday
backups/20251205_140000/  # 2 PM today (corrupted around this time)
backups/20251204_020000/  # 2 AM day before (known good)
```

---

## What Gets Backed Up

| Database | Backed Up | Format | Size |
|----------|-----------|--------|------|
| **PostgreSQL** | ✅ Yes | Custom dump | ~50MB (full chat history) |
| **Qdrant** | ✅ Yes | Snapshot tarball | ~200MB (embeddings) |
| **Neo4j** | ✅ Yes | Cypher statements | ~10MB (knowledge graph) |
| **InfluxDB** | ✅ Yes | Native backup | ~20MB (metrics) |

---

## Backup Verification

After backup, verify files exist:

```bash
# Check latest backup
LATEST=$(ls -t backups/ | head -1)
ls -lh backups/$LATEST/

# Expected output:
# -rw-r--r-- ... 45M influxdb/
# -rw-r--r-- ... 5.2M neo4j.cypher
# -rw-r--r--  ... 120M postgres.dump
# -rw-r--r-- ... 185M qdrant_snapshot.tar
```

## Environment Variables

The backup/restore scripts use credentials from environment:

```bash
# Optional - defaults to docker-compose.yml values
export NEO4J_PASSWORD=password
export INFLUXDB_TOKEN=my-super-secret-auth-token
```

If credentials change in docker-compose.yml, update the scripts:

```bash
# In scripts/backup.sh, line ~38-40
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"
INFLUXDB_TOKEN="${INFLUXDB_TOKEN:-my-super-secret-auth-token}"
```

---

## Troubleshooting

### "Container not running"

```bash
# Ensure all containers are up
./bot.sh up all -d
sleep 10
./scripts/backup.sh
```

### "Failed to create Qdrant snapshot"

- Qdrant may be starting up. Restart and try again:
```bash
docker restart whisperengine-v2-qdrant
sleep 5
./scripts/backup.sh
```

### "Neo4j backup is empty"

Neo4j APOC extension not available. This is OK - basic export will be used.

### Restore Fails

```bash
# 1. Check if containers are running
docker ps | grep whisperengine

# 2. Check database credentials
docker exec whisperengine-v2-postgres psql -U whisper -d whisperengine_v2 -c "\dt"

# 3. Check logs
docker logs whisperengine-v2-postgres | tail -20
```

---

## Best Practices

✅ **DO:**
- Run backups regularly (daily recommended)
- Test restore process monthly
- Keep backups in multiple locations (local + cloud)
- Monitor backup sizes for trends
- Document recovery procedures

❌ **DON'T:**
- Run backup while heavy messages are being processed
- Delete backups immediately after restore
- Restore without confirming database is not in use
- Restore older backups without knowing why

---

## Backup Retention

Keep backups based on importance:

```bash
# Daily backups for 7 days
find backups/ -mtime +7 -exec rm -rf {} \;

# Weekly backups for 4 weeks
find backups/ -name "*_020000" -mtime +28 -exec rm -rf {} \;

# Monthly backups forever (just archive)
```

---

## Advanced: Custom Backup Locations

For Docker volumes instead of host filesystem:

```bash
# Create backup volume
docker volume create whisperengine_backups

# Backup to volume
docker run --rm \
  -v whisperengine-v2_postgres_data_v2:/source \
  -v whisperengine_backups:/backups \
  alpine tar czf /backups/postgres_$(date +%Y%m%d_%H%M%S).tar.gz -C /source .
```

---

## Recent Updates (Dec 5, 2025)

- ✅ Added cron automation support
- ✅ Improved error handling for all databases
- ✅ Added environment variable support for credentials
- ✅ Better diagnostic messages
- ✅ Documented disaster recovery procedures

**Last tested**: Dec 5, 2025 - Successfully recovered from database corruption
**Next recommendation**: Set up automated daily backups via cron

---

**Questions?** Check logs in `backups/cron.log` if running via cron, or run manually for detailed output.
