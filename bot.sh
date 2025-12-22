#!/bin/bash
# WhisperEngine v2 - Bot Management Script

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

INFRA_SERVICES="postgres qdrant neo4j influxdb redis"
BOT_SERVICES="elena ryan dotty aria dream jake sophia marcus nottaylor gabriel aethys aetheris"
WORKER_SERVICES="worker-cognition worker-action worker-sensory worker-social"

show_help() {
    echo -e "${BLUE}WhisperEngine v2 - Bot Management${NC}"
    echo ""
    echo "Usage: ./bot.sh [command] [target]"
    echo ""
    echo "Targets:"
    echo "  all          Everything (default)"
    echo "  infra        Infrastructure (databases)"
    echo "  bots         All bot containers"
    echo "  workers      All background workers"
    echo "  <name>       Specific service (e.g., elena, postgres)"
    echo ""
    echo "Commands:"
    echo "  up           Start/Update containers (builds if needed)"
    echo "  down         Stop and remove containers"
    echo "  start        Start existing containers"
    echo "  stop         Stop running containers"
    echo "  restart      Restart containers"
    echo "  logs         View logs"
    echo "  ps           Show status"
    echo "  build        Rebuild images"
    echo "  backup       Backup databases"
    echo "  restore      Restore databases"
    echo ""
    echo "Environment Modes:"
    echo "  Development (default):"
    echo "    - Uses docker-compose.override.yml"
    echo "    - Live code reload (source mounted)"
    echo "  Production:"
    echo "    - Set COMPOSE_FILE=docker-compose.yml"
    echo "    - Baked code (rebuild required for changes)"
    echo ""
    echo "Examples:"
    echo "  ./bot.sh up infra                        # Start databases (dev)"
    echo "  ./bot.sh up elena                        # Start Elena (dev)"
    echo "  ./bot.sh restart bots                    # Restart all bots (dev)"
    echo "  COMPOSE_FILE=docker-compose.yml ./bot.sh up elena  # Production mode"
    echo ""
}

# Helper: Check if target is a single bot (needs --profile for 'up')
is_bot() {
    local target=$1
    for bot in $BOT_SERVICES; do
        [ "$target" = "$bot" ] && return 0
    done
    return 1
}

# Helper: Resolve target alias to service names
resolve_target() {
    local target=$1
    case "$target" in
        all)         echo "ALL" ;;
        infra)       echo "$INFRA_SERVICES" ;;
        bots)        echo "$BOT_SERVICES" ;;
        workers)     echo "$WORKER_SERVICES" ;;
        worker)      echo "$WORKER_SERVICES" ;; # Alias
        *)           echo "$target" ;;
    esac
}

# Main Command Handler
CMD=$1
TARGET=$2

# Handle commands that don't take a target or have specific handling
case "$CMD" in
    ps)
        docker compose ps
        exit 0
        ;;
    build)
        echo -e "${YELLOW}Building images...${NC}"
        docker compose build
        echo -e "${GREEN}✓ Build complete${NC}"
        exit 0
        ;;
    backup)
        ./scripts/backup.sh
        exit 0
        ;;
    restore)
        if [ -z "$TARGET" ]; then
            echo -e "${RED}Error: Please specify backup directory${NC}"
            exit 1
        fi
        ./scripts/restore.sh "$TARGET"
        exit 0
        ;;
    help|--help|-h|"")
        show_help
        exit 0
        ;;
esac

# Require explicit target for lifecycle commands (safety)
if [ -z "$TARGET" ]; then
    echo -e "${RED}Error: Please specify a target (all, infra, bots, workers, or service name)${NC}"
    echo ""
    show_help
    exit 1
fi

# Resolve services for lifecycle commands
SERVICES=$(resolve_target "$TARGET")

if [ -z "$SERVICES" ]; then
    echo -e "${RED}Error: Unknown target '$TARGET'${NC}"
    exit 1
fi

case "$CMD" in
    up)
        if [ "$SERVICES" = "ALL" ]; then
            echo -e "${YELLOW}Starting everything...${NC}"
            docker compose --profile all up -d --build
        elif is_bot "$TARGET"; then
            # Single bot requires --profile since bots use Docker profiles
            echo -e "${YELLOW}Starting $TARGET...${NC}"
            docker compose --profile "$TARGET" up -d --build
        else
            echo -e "${YELLOW}Starting $TARGET...${NC}"
            docker compose up -d --build $SERVICES
        fi
        echo -e "${GREEN}✓ Up complete${NC}"
        ;;

    down)
        if [ "$SERVICES" = "ALL" ]; then
            echo -e "${YELLOW}Stopping everything...${NC}"
            docker compose --profile all down
        else
            echo -e "${YELLOW}Stopping $TARGET...${NC}"
            docker compose stop $SERVICES
            docker compose rm -f $SERVICES
        fi
        echo -e "${GREEN}✓ Down complete${NC}"
        ;;

    start)
        if [ "$SERVICES" = "ALL" ]; then
            echo -e "${YELLOW}Starting everything...${NC}"
            # Neo4j workaround
            docker compose stop neo4j >/dev/null 2>&1 || true
            docker compose rm -f neo4j >/dev/null 2>&1 || true
            docker compose --profile all up -d --no-build
        else
            echo -e "${YELLOW}Starting $TARGET...${NC}"
            docker compose up -d --no-build $SERVICES
        fi
        echo -e "${GREEN}✓ Started${NC}"
        ;;

    stop)
        if [ "$SERVICES" = "ALL" ]; then
            echo -e "${YELLOW}Stopping everything...${NC}"
            docker compose --profile all stop
        else
            echo -e "${YELLOW}Stopping $TARGET...${NC}"
            docker compose stop $SERVICES
        fi
        echo -e "${GREEN}✓ Stopped${NC}"
        ;;

    restart)
        if [ "$SERVICES" = "ALL" ]; then
            echo -e "${YELLOW}Restarting everything...${NC}"
            docker compose --profile all restart
        else
            echo -e "${YELLOW}Restarting $TARGET...${NC}"
            docker compose restart $SERVICES
        fi
        echo -e "${GREEN}✓ Restarted${NC}"
        ;;

    logs)
        if [ "$SERVICES" = "ALL" ]; then
            docker compose --profile all logs -f
        else
            docker compose logs -f $SERVICES
        fi
        ;;

    *)
        echo -e "${RED}Unknown command: $CMD${NC}"
        show_help
        exit 1
        ;;
esac

exit 0
