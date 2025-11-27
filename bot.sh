#!/bin/bash
# WhisperEngine v2 - Bot Management Script

set -e

COMPOSE_FILE="docker-compose.yml"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

INFRA_SERVICES="postgres qdrant neo4j influxdb redis"

show_help() {
    echo -e "${BLUE}WhisperEngine v2 - Bot Management${NC}"
    echo ""
    echo "Usage: ./bot.sh [command]"
    echo ""
    echo "Commands:"
    echo "  infra [up|down]       Start or stop infrastructure services"
    echo "  up [bot|all]          Start infrastructure + bot(s) (builds images)"
    echo "  down [bot|all]        Stop and remove containers"
    echo "  start [bot|all]       Start existing containers (no build)"
    echo "  stop [bot|all]        Stop running containers"
    echo "  restart [bot|all]     Restart containers"
    echo "  logs [bot|all]        Show logs"
    echo "  ps                    Show status of all containers"
    echo "  build                 Rebuild bot images"
    echo "  backup                Backup all databases"
    echo "  restore <dir>         Restore databases from backup"
    echo ""
    echo "Examples:"
    echo "  ./bot.sh infra up     # Start just databases"
    echo "  ./bot.sh up elena     # Start infrastructure + Elena"
    echo "  ./bot.sh up all       # Start everything"
    echo "  ./bot.sh stop elena   # Stop Elena"
    echo "  ./bot.sh start elena  # Start Elena"
    echo "  ./bot.sh logs elena   # Watch Elena's logs"
    echo "  ./bot.sh restart elena # Restart Elena"
    echo "  ./bot.sh backup       # Backup all databases"
    echo "  ./bot.sh restore ./backups/20251126_120000  # Restore from backup"
    echo ""
}

case "$1" in
    infra)
        if [ "$2" = "up" ]; then
            echo -e "${YELLOW}Starting infrastructure...${NC}"
            docker compose up -d $INFRA_SERVICES
            echo -e "${GREEN}✓ Infrastructure started${NC}"
            docker compose ps
        elif [ "$2" = "down" ]; then
            echo -e "${YELLOW}Stopping infrastructure...${NC}"
            docker compose stop $INFRA_SERVICES
            docker compose rm -f $INFRA_SERVICES
            echo -e "${GREEN}✓ Infrastructure stopped${NC}"
        else
            echo -e "${RED}Error: Specify action${NC}"
            echo "Usage: ./bot.sh infra [up|down]"
            exit 1
        fi
        ;;
    
    up)
        if [ "$2" = "all" ]; then
            echo -e "${YELLOW}Starting all bots...${NC}"
            docker compose --profile all up -d --build
        elif [ -n "$2" ]; then
            echo -e "${YELLOW}Starting $2...${NC}"
            docker compose --profile "$2" up -d --build
        else
            echo -e "${RED}Error: Specify bot name or 'all'${NC}"
            echo "Usage: ./bot.sh up [bot|all]"
            echo "Bots: elena, ryan, dotty, aria, dream, jake, sophia, marcus, nottaylor"
            exit 1
        fi
        echo -e "${GREEN}✓ Deployment complete${NC}"
        sleep 5
        docker ps --filter "name=whisperengine-v2-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ;;
    
    down)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Specify bot name or 'all'${NC}"
            echo "Usage: ./bot.sh down [bot|all]"
            echo "Bots: elena, ryan, dotty, aria, dream, jake, sophia, marcus, nottaylor"
            exit 1
        fi

        if [ "$2" = "all" ]; then
            echo -e "${YELLOW}Stopping all containers...${NC}"
            docker compose --profile all down
            echo -e "${GREEN}✓ All containers stopped${NC}"
        else
            echo -e "${YELLOW}Stopping and removing $2...${NC}"
            docker compose stop "$2"
            docker compose rm -f "$2"
            echo -e "${GREEN}✓ $2 removed${NC}"
        fi
        ;;
    
    stop)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Specify bot name or 'all'${NC}"
            echo "Usage: ./bot.sh stop [bot|all]"
            echo "Bots: elena, ryan, dotty, aria, dream, jake, sophia, marcus, nottaylor"
            exit 1
        fi

        if [ "$2" = "all" ]; then
            echo -e "${YELLOW}Stopping all bots...${NC}"
            docker compose --profile all stop
        else
            echo -e "${YELLOW}Stopping $2...${NC}"
            docker compose stop "$2"
        fi
        echo -e "${GREEN}✓ Stopped${NC}"
        ;;

    start)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Specify bot name or 'all'${NC}"
            echo "Usage: ./bot.sh start [bot|all]"
            echo "Bots: elena, ryan, dotty, aria, dream, jake, sophia, marcus, nottaylor"
            exit 1
        fi

        if [ "$2" = "all" ]; then
            echo -e "${YELLOW}Starting all bots...${NC}"
            # Neo4j workaround: Force recreate to prevent restart loops
            docker compose stop neo4j >/dev/null 2>&1 || true
            docker compose rm -f neo4j >/dev/null 2>&1 || true
            docker compose --profile all up -d --no-build
        else
            echo -e "${YELLOW}Starting $2...${NC}"
            docker compose up -d --no-build "$2"
        fi
        echo -e "${GREEN}✓ Started${NC}"
        ;;
    
    restart)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Specify bot name or 'all'${NC}"
            echo "Usage: ./bot.sh restart [bot|all]"
            echo "Bots: elena, ryan, dotty, aria, dream, jake, sophia, marcus, nottaylor"
            exit 1
        fi

        if [ "$2" = "all" ]; then
            echo -e "${YELLOW}Restarting all bots...${NC}"
            docker compose --profile all restart
        else
            echo -e "${YELLOW}Restarting $2...${NC}"
            docker compose restart "$2"
        fi
        echo -e "${GREEN}✓ Restarted${NC}"
        ;;
    
    logs)
        if [ "$2" = "all" ] || [ -z "$2" ]; then
            docker compose --profile all logs -f
        else
            docker compose logs -f "$2"
        fi
        ;;
    
    ps)
        docker compose ps
        ;;
    
    build)
        echo -e "${YELLOW}Building bot images...${NC}"
        docker compose build
        echo -e "${GREEN}✓ Build complete${NC}"
        ;;
    
    backup)
        ./scripts/backup.sh
        ;;
    
    restore)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please specify backup directory${NC}"
            echo "Usage: ./bot.sh restore <backup_directory>"
            echo ""
            echo "Available backups:"
            ls -d ./backups/*/ 2>/dev/null || echo "  No backups found"
            exit 1
        fi
        ./scripts/restore.sh "$2"
        ;;
    
    help|--help|-h|"")
        show_help
        ;;
    
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
