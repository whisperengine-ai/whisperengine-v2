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

show_help() {
    echo -e "${BLUE}WhisperEngine v2 - Bot Management${NC}"
    echo ""
    echo "Usage: ./bot.sh [command]"
    echo ""
    echo "Commands:"
    echo "  infra                  Start only infrastructure"
    echo "  up [bot]              Start infrastructure + specific bot (elena, ryan, dotty, aria, dream)"
    echo "  up all                Start infrastructure + all bots"
    echo "  down                  Stop all containers"
    echo "  restart [bot]         Restart specific bot"
    echo "  logs [bot]            Show logs for specific bot (or 'all')"
    echo "  ps                    Show status of all containers"
    echo "  build                 Rebuild bot images"
    echo ""
    echo "Examples:"
    echo "  ./bot.sh infra        # Start just databases"
    echo "  ./bot.sh up elena     # Start infrastructure + Elena"
    echo "  ./bot.sh up all       # Start everything"
    echo "  ./bot.sh logs elena   # Watch Elena's logs"
    echo "  ./bot.sh restart elena # Restart Elena"
    echo ""
}

case "$1" in
    infra)
        echo -e "${YELLOW}Starting infrastructure...${NC}"
        docker compose up -d
        echo -e "${GREEN}✓ Infrastructure started${NC}"
        docker ps --filter "name=whisperengine-v2-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
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
            echo "Usage: ./bot.sh up [elena|ryan|dotty|aria|dream|all]"
            exit 1
        fi
        echo -e "${GREEN}✓ Deployment complete${NC}"
        sleep 5
        docker ps --filter "name=whisperengine-v2-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ;;
    
    down)
        echo -e "${YELLOW}Stopping all containers...${NC}"
        docker compose --profile all down
        echo -e "${GREEN}✓ All containers stopped${NC}"
        ;;
    
    restart)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Specify bot name${NC}"
            echo "Usage: ./bot.sh restart [elena|ryan|dotty|aria|dream]"
            exit 1
        fi
        echo -e "${YELLOW}Restarting $2...${NC}"
        docker compose restart "$2"
        echo -e "${GREEN}✓ $2 restarted${NC}"
        ;;
    
    logs)
        if [ "$2" = "all" ] || [ -z "$2" ]; then
            docker compose --profile all logs -f
        else
            docker logs -f "whisperengine-v2-$2"
        fi
        ;;
    
    ps)
        docker ps --filter "name=whisperengine-v2-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ;;
    
    build)
        echo -e "${YELLOW}Building bot images...${NC}"
        docker compose build
        echo -e "${GREEN}✓ Build complete${NC}"
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
