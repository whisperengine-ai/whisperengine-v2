#!/bin/bash
# WhisperEngine v2 - Database Backup Script
# Backs up PostgreSQL, Qdrant, Neo4j, and InfluxDB to a timestamped directory
#
# Usage:
#   ./scripts/backup.sh                    # Manual backup
#   BACKUP_DIR=/backups ./scripts/backup.sh # Custom backup location
#
# For automated backups, add to crontab:
#   0 2 * * * cd /path/to/whisperengine-v2 && ./scripts/backup.sh
#   (Runs backup every day at 2 AM)

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
BACKUP_ROOT="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"

# Container names (from docker-compose.yml)
POSTGRES_CONTAINER="whisperengine-v2-postgres"
QDRANT_CONTAINER="whisperengine-v2-qdrant"
NEO4J_CONTAINER="whisperengine-v2-neo4j"
INFLUXDB_CONTAINER="whisperengine-v2-influxdb"

# Postgres credentials (from docker-compose.yml)
POSTGRES_USER="whisper"
POSTGRES_DB="whisperengine_v2"

# Neo4j credentials (from docker-compose.yml)
NEO4J_USER="neo4j"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"

# InfluxDB credentials (from docker-compose.yml)
INFLUXDB_ORG="whisperengine"
INFLUXDB_TOKEN="${INFLUXDB_TOKEN:-my-super-secret-auth-token}"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  WhisperEngine v2 - Database Backup    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "Backup directory: ${YELLOW}$BACKUP_DIR${NC}"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# ============================================
# PostgreSQL Backup
# ============================================
echo -e "${YELLOW}[1/4] Backing up PostgreSQL...${NC}"
if docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    if docker exec "$POSTGRES_CONTAINER" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom > "$BACKUP_DIR/postgres.dump" 2>/dev/null; then
        SIZE=$(du -h "$BACKUP_DIR/postgres.dump" | cut -f1)
        echo -e "${GREEN}  ✓ PostgreSQL backed up ($SIZE)${NC}"
    else
        echo -e "${RED}  ✗ PostgreSQL backup failed${NC}"
        exit 1
    fi
else
    echo -e "${RED}  ✗ PostgreSQL container not running${NC}"
    exit 1
fi

# ============================================
# Qdrant Backup (Snapshot)
# ============================================
echo -e "${YELLOW}[2/4] Backing up Qdrant...${NC}"
if docker ps --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER}$"; then
    # Create snapshot via API
    SNAPSHOT_RESPONSE=$(curl -s -X POST "http://localhost:6333/snapshots" 2>/dev/null || echo '{}')
    SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESPONSE" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
    
    if [ -n "$SNAPSHOT_NAME" ]; then
        # Download the snapshot
        if curl -s "http://localhost:6333/snapshots/$SNAPSHOT_NAME" -o "$BACKUP_DIR/qdrant_snapshot.tar" 2>/dev/null; then
            SIZE=$(du -h "$BACKUP_DIR/qdrant_snapshot.tar" | cut -f1)
            echo -e "${GREEN}  ✓ Qdrant backed up ($SIZE)${NC}"
            
            # Clean up remote snapshot
            curl -s -X DELETE "http://localhost:6333/snapshots/$SNAPSHOT_NAME" > /dev/null 2>&1 || true
        else
            echo -e "${RED}  ✗ Failed to download Qdrant snapshot${NC}"
        fi
    else
        echo -e "${YELLOW}  ⚠ Failed to create Qdrant snapshot (no data?)${NC}"
    fi
else
    echo -e "${RED}  ✗ Qdrant container not running${NC}"
fi

# ============================================
# Neo4j Backup (Cypher dump)
# ============================================
echo -e "${YELLOW}[3/4] Backing up Neo4j...${NC}"
if docker ps --format '{{.Names}}' | grep -q "^${NEO4J_CONTAINER}$"; then
    # Check if APOC is available
    HAS_APOC=$(docker exec "$NEO4J_CONTAINER" cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
        "RETURN apoc.version()" 2>/dev/null | grep -i version | wc -l)
    
    if [ "$HAS_APOC" -gt 0 ]; then
        # Use APOC to export all nodes and relationships
        if docker exec "$NEO4J_CONTAINER" cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
            "CALL apoc.export.cypher.all(null, {format: 'plain'}) YIELD cypherStatements RETURN cypherStatements" \
            > "$BACKUP_DIR/neo4j.cypher" 2>/dev/null; then
            SIZE=$(du -h "$BACKUP_DIR/neo4j.cypher" | cut -f1)
            echo -e "${GREEN}  ✓ Neo4j backed up ($SIZE)${NC}"
        else
            echo -e "${YELLOW}  ⚠ Neo4j backup may have failed${NC}"
        fi
    else
        # Fallback: basic node/relationship export
        echo -e "${YELLOW}  APOC not available, using basic export...${NC}"
        docker exec "$NEO4J_CONTAINER" cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
            "MATCH (n) RETURN labels(n) as labels, properties(n) as props" \
            --format plain > "$BACKUP_DIR/neo4j_nodes.txt" 2>/dev/null || true
        
        if [ -s "$BACKUP_DIR/neo4j_nodes.txt" ]; then
            SIZE=$(du -h "$BACKUP_DIR/neo4j_nodes.txt" | cut -f1)
            echo -e "${GREEN}  ✓ Neo4j nodes backed up ($SIZE - basic format)${NC}"
        else
            echo -e "${YELLOW}  ⚠ Neo4j backup is empty (no data?)${NC}"
        fi
    fi
else
    echo -e "${RED}  ✗ Neo4j container not running${NC}"
fi

# ============================================
# InfluxDB Backup
# ============================================
echo -e "${YELLOW}[4/4] Backing up InfluxDB...${NC}"
if docker ps --format '{{.Names}}' | grep -q "^${INFLUXDB_CONTAINER}$"; then
    if docker exec "$INFLUXDB_CONTAINER" influx backup /tmp/influx_backup \
        --org "$INFLUXDB_ORG" \
        --token "$INFLUXDB_TOKEN" \
        2>/dev/null; then
        
        # Copy backup out of container
        if docker cp "$INFLUXDB_CONTAINER:/tmp/influx_backup" "$BACKUP_DIR/influxdb" 2>/dev/null; then
            SIZE=$(du -sh "$BACKUP_DIR/influxdb" 2>/dev/null | cut -f1)
            echo -e "${GREEN}  ✓ InfluxDB backed up ($SIZE)${NC}"
            
            # Cleanup inside container
            docker exec "$INFLUXDB_CONTAINER" rm -rf /tmp/influx_backup 2>/dev/null || true
        else
            echo -e "${RED}  ✗ Failed to copy InfluxDB backup${NC}"
        fi
    else
        echo -e "${YELLOW}  ⚠ InfluxDB backup failed or empty${NC}"
    fi
else
    echo -e "${RED}  ✗ InfluxDB container not running${NC}"
fi

# ============================================
# Summary
# ============================================
echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
echo -e "${GREEN}Backup complete!${NC}"
echo -e "Location: ${YELLOW}$BACKUP_DIR${NC}"
echo -e "Total size: ${YELLOW}$TOTAL_SIZE${NC}"
echo ""
echo "Contents:"
ls -lh "$BACKUP_DIR"
echo ""
echo -e "${BLUE}To restore: ${NC}./scripts/restore.sh $BACKUP_DIR"
echo ""
