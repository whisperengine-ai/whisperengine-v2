#!/bin/bash
# WhisperEngine v2 - Database Backup Script
# Backs up PostgreSQL, Qdrant, Neo4j, and InfluxDB to a timestamped directory

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
    docker exec "$POSTGRES_CONTAINER" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom > "$BACKUP_DIR/postgres.dump"
    echo -e "${GREEN}  ✓ PostgreSQL backed up ($(du -h "$BACKUP_DIR/postgres.dump" | cut -f1))${NC}"
else
    echo -e "${RED}  ✗ PostgreSQL container not running, skipping${NC}"
fi

# ============================================
# Qdrant Backup (Snapshot)
# ============================================
echo -e "${YELLOW}[2/4] Backing up Qdrant...${NC}"
if docker ps --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER}$"; then
    # Create snapshot via API
    SNAPSHOT_RESPONSE=$(curl -s -X POST "http://localhost:6333/snapshots")
    SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESPONSE" | grep -o '"name":"[^"]*"' | head -1 | cut -d'"' -f4)
    
    if [ -n "$SNAPSHOT_NAME" ]; then
        # Download the snapshot
        curl -s "http://localhost:6333/snapshots/$SNAPSHOT_NAME" -o "$BACKUP_DIR/qdrant_snapshot.tar"
        echo -e "${GREEN}  ✓ Qdrant backed up ($(du -h "$BACKUP_DIR/qdrant_snapshot.tar" | cut -f1))${NC}"
        
        # Clean up remote snapshot
        curl -s -X DELETE "http://localhost:6333/snapshots/$SNAPSHOT_NAME" > /dev/null
    else
        echo -e "${RED}  ✗ Failed to create Qdrant snapshot${NC}"
    fi
else
    echo -e "${RED}  ✗ Qdrant container not running, skipping${NC}"
fi

# ============================================
# Neo4j Backup (Cypher dump)
# ============================================
echo -e "${YELLOW}[3/4] Backing up Neo4j...${NC}"
if docker ps --format '{{.Names}}' | grep -q "^${NEO4J_CONTAINER}$"; then
    # Use cypher-shell to export all nodes and relationships
    docker exec "$NEO4J_CONTAINER" cypher-shell -u neo4j -p password \
        "CALL apoc.export.cypher.all(null, {format: 'plain', stream: true}) YIELD cypherStatements RETURN cypherStatements" \
        2>/dev/null > "$BACKUP_DIR/neo4j.cypher" || {
        # Fallback: export nodes as JSON if APOC not available
        echo -e "${YELLOW}  APOC not available, using basic export...${NC}"
        docker exec "$NEO4J_CONTAINER" cypher-shell -u neo4j -p password \
            "MATCH (n) RETURN labels(n) as labels, properties(n) as props" \
            --format plain > "$BACKUP_DIR/neo4j_nodes.txt" 2>/dev/null
        docker exec "$NEO4J_CONTAINER" cypher-shell -u neo4j -p password \
            "MATCH (a)-[r]->(b) RETURN labels(a), id(a), type(r), properties(r), labels(b), id(b)" \
            --format plain > "$BACKUP_DIR/neo4j_rels.txt" 2>/dev/null
    }
    
    # Check if we got any output
    if [ -s "$BACKUP_DIR/neo4j.cypher" ] || [ -s "$BACKUP_DIR/neo4j_nodes.txt" ]; then
        NEO4J_SIZE=$(du -ch "$BACKUP_DIR"/neo4j* 2>/dev/null | tail -1 | cut -f1)
        echo -e "${GREEN}  ✓ Neo4j backed up ($NEO4J_SIZE)${NC}"
    else
        echo -e "${YELLOW}  ⚠ Neo4j backup may be empty (no data?)${NC}"
    fi
else
    echo -e "${RED}  ✗ Neo4j container not running, skipping${NC}"
fi

# ============================================
# InfluxDB Backup
# ============================================
echo -e "${YELLOW}[4/4] Backing up InfluxDB...${NC}"
if docker ps --format '{{.Names}}' | grep -q "^${INFLUXDB_CONTAINER}$"; then
    # Use influx CLI to backup
    docker exec "$INFLUXDB_CONTAINER" influx backup /tmp/influx_backup \
        --org whisperengine \
        --token my-super-secret-auth-token \
        2>/dev/null
    
    # Copy backup out of container
    docker cp "$INFLUXDB_CONTAINER:/tmp/influx_backup" "$BACKUP_DIR/influxdb"
    
    # Cleanup inside container
    docker exec "$INFLUXDB_CONTAINER" rm -rf /tmp/influx_backup
    
    INFLUX_SIZE=$(du -sh "$BACKUP_DIR/influxdb" 2>/dev/null | cut -f1)
    echo -e "${GREEN}  ✓ InfluxDB backed up ($INFLUX_SIZE)${NC}"
else
    echo -e "${RED}  ✗ InfluxDB container not running, skipping${NC}"
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
