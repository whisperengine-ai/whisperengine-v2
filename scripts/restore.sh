#!/bin/bash
# WhisperEngine v2 - Database Restore Script
# Restores PostgreSQL, Qdrant, Neo4j, and InfluxDB from a backup directory
#
# IMPORTANT: This will OVERWRITE existing data. Use with caution!
#
# Usage:
#   ./scripts/restore.sh ./backups/20251205_135600
#
# Note: This script requires containers to be running

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check argument
if [ -z "$1" ]; then
    echo -e "${RED}Error: Please specify backup directory${NC}"
    echo ""
    echo "Usage: ./scripts/restore.sh <backup_directory>"
    echo ""
    echo "Available backups:"
    ls -d ./backups/*/ 2>/dev/null || echo "  No backups found in ./backups/"
    exit 1
fi

BACKUP_DIR="$1"

if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}Error: Backup directory not found: $BACKUP_DIR${NC}"
    exit 1
fi

# Container names
POSTGRES_CONTAINER="whisperengine-v2-postgres"
QDRANT_CONTAINER="whisperengine-v2-qdrant"
NEO4J_CONTAINER="whisperengine-v2-neo4j"
INFLUXDB_CONTAINER="whisperengine-v2-influxdb"

# Postgres credentials
POSTGRES_USER="whisper"
POSTGRES_DB="whisperengine_v2"

# Neo4j credentials (from docker-compose.yml)
NEO4J_USER="neo4j"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"

# InfluxDB credentials
INFLUXDB_ORG="whisperengine"
INFLUXDB_TOKEN="${INFLUXDB_TOKEN:-my-super-secret-auth-token}"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  WhisperEngine v2 - Database Restore   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "Restoring from: ${YELLOW}$BACKUP_DIR${NC}"
echo ""

# Confirm
echo -e "${RED}⚠️  WARNING: This will OVERWRITE existing data!${NC}"
read -p "Are you sure you want to continue? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""

# ============================================
# PostgreSQL Restore
# ============================================
if [ -f "$BACKUP_DIR/postgres.dump" ]; then
    echo -e "${YELLOW}[1/4] Restoring PostgreSQL...${NC}"
    if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
        # Drop and recreate database
        if docker exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};" postgres 2>/dev/null; then
            docker exec "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -c "CREATE DATABASE ${POSTGRES_DB};" postgres
            
            # Restore from dump
            if cat "$BACKUP_DIR/postgres.dump" | docker exec -i "$POSTGRES_CONTAINER" pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl 2>/dev/null; then
                echo -e "${GREEN}  ✓ PostgreSQL restored${NC}"
            else
                echo -e "${YELLOW}  ⚠ PostgreSQL restore completed with warnings${NC}"
            fi
        fi
    else
        echo -e "${RED}  ✗ PostgreSQL container not running${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}[1/4] No PostgreSQL backup found, skipping${NC}"
fi

# ============================================
# Qdrant Restore
# ============================================
if [ -f "$BACKUP_DIR/qdrant_snapshot.tar" ]; then
    echo -e "${YELLOW}[2/4] Restoring Qdrant...${NC}"
    if docker ps --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER}$"; then
        # Copy snapshot to container
        docker cp "$BACKUP_DIR/qdrant_snapshot.tar" "$QDRANT_CONTAINER:/qdrant/snapshots/restore.tar" 2>/dev/null
        
        # Restore via API
        if curl -s -X POST "http://localhost:6333/snapshots/recover" \
            -H "Content-Type: application/json" \
            -d "{\"location\": \"file:///qdrant/snapshots/restore.tar\"}" 2>/dev/null | grep -q "success\|recovered"; then
            echo -e "${GREEN}  ✓ Qdrant restored${NC}"
        else
            echo -e "${YELLOW}  ⚠ Qdrant restore may have completed with warnings${NC}"
        fi
        
        # Cleanup
        docker exec "$QDRANT_CONTAINER" rm -f /qdrant/snapshots/restore.tar 2>/dev/null || true
    else
        echo -e "${RED}  ✗ Qdrant container not running${NC}"
    fi
else
    echo -e "${YELLOW}[2/4] No Qdrant backup found, skipping${NC}"
fi

# ============================================
# Neo4j Restore
# ============================================
if [ -f "$BACKUP_DIR/neo4j.cypher" ]; then
    echo -e "${YELLOW}[3/4] Restoring Neo4j...${NC}"
    if docker ps --format '{{.Names}}' | grep -q "^${NEO4J_CONTAINER}$"; then
        # Clear existing data
        docker exec "$NEO4J_CONTAINER" cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
            "MATCH (n) DETACH DELETE n" 2>/dev/null || echo -e "${YELLOW}  (Clearing existing data...)${NC}"
        
        # Restore from cypher statements (with better error handling)
        if cat "$BACKUP_DIR/neo4j.cypher" | docker exec -i "$NEO4J_CONTAINER" cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" 2>/dev/null; then
            echo -e "${GREEN}  ✓ Neo4j restored${NC}"
        else
            echo -e "${YELLOW}  ⚠ Neo4j restore completed (check logs for details)${NC}"
        fi
    else
        echo -e "${RED}  ✗ Neo4j container not running${NC}"
    fi
elif [ -f "$BACKUP_DIR/neo4j_nodes.txt" ]; then
    echo -e "${YELLOW}[3/4] Neo4j backup found in basic format - manual restore required${NC}"
    echo -e "  ${YELLOW}Files: $BACKUP_DIR/neo4j_nodes.txt, $BACKUP_DIR/neo4j_rels.txt${NC}"
    echo -e "  ${YELLOW}Please review these files and import manually if needed${NC}"
else
    echo -e "${YELLOW}[3/4] No Neo4j backup found, skipping${NC}"
fi

# ============================================
# InfluxDB Restore
# ============================================
if [ -d "$BACKUP_DIR/influxdb" ]; then
    echo -e "${YELLOW}[4/4] Restoring InfluxDB...${NC}"
    if docker ps --format '{{.Names}}' | grep -q "^${INFLUXDB_CONTAINER}$"; then
        # Copy backup to container
        docker cp "$BACKUP_DIR/influxdb" "$INFLUXDB_CONTAINER:/tmp/influx_restore" 2>/dev/null
        
        # Restore using influx CLI
        if docker exec "$INFLUXDB_CONTAINER" influx restore /tmp/influx_restore \
            --org "$INFLUXDB_ORG" \
            --token "$INFLUXDB_TOKEN" \
            --full 2>/dev/null | grep -q "success\|restore"; then
            echo -e "${GREEN}  ✓ InfluxDB restored${NC}"
        else
            echo -e "${YELLOW}  ⚠ InfluxDB restore completed (check logs for details)${NC}"
        fi
        
        # Cleanup
        docker exec "$INFLUXDB_CONTAINER" rm -rf /tmp/influx_restore 2>/dev/null || true
    else
        echo -e "${RED}  ✗ InfluxDB container not running${NC}"
    fi
else
    echo -e "${YELLOW}[4/4] No InfluxDB backup found, skipping${NC}"
fi

# ============================================
# Summary
# ============================================
echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${GREEN}Restore complete!${NC}"
echo ""
echo -e "${YELLOW}⚠️  Recommended: Restart your bots to reconnect to restored databases${NC}"
echo "   ./bot.sh restart all"
echo ""
