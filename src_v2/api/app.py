"""
WhisperEngine Chat API Application

FastAPI application factory for the WhisperEngine Chat API.
Each bot instance runs its own API server on a unique port.

Swagger UI: http://localhost:{PORT}/docs
ReDoc: http://localhost:{PORT}/redoc
OpenAPI JSON: http://localhost:{PORT}/openapi.json
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger
from src_v2.api.routes import router
from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.memory.manager import memory_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.core.character import character_manager
from src_v2.universe.manager import universe_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing API resources (Worker Mode)...")
    await db_manager.connect_all()
    await memory_manager.initialize()
    await knowledge_manager.initialize()
    await universe_manager.initialize()
    
    # Load character if configured
    if settings.DISCORD_BOT_NAME:
        logger.info(f"Loading character: {settings.DISCORD_BOT_NAME}...")
        character_manager.load_character(settings.DISCORD_BOT_NAME)
    
    yield
    
    # Shutdown
    logger.info("Shutting down API resources...")
    await db_manager.disconnect_all()


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        lifespan=lifespan,
        title="WhisperEngine Chat API",
        version="2.0.0",
        description="""
## WhisperEngine v2 Chat API

Interact with AI characters that remember, learn, and evolve.

### Features

- **Persistent Memory**: Characters remember your conversations across sessions
- **Knowledge Graph**: Characters learn facts about you and use them contextually  
- **Relationship Evolution**: Trust and familiarity grow over time
- **Multiple Characters**: Each bot has its own personality and memory

### Quick Start

```bash
curl -X POST http://localhost:8000/api/chat \\
  -H "Content-Type: application/json" \\
  -d '{"user_id": "test_user", "message": "Hello!"}'
```

See [API Documentation](/docs/API_REFERENCE.md) for full details.
        """,
        contact={
            "name": "WhisperEngine",
            "url": "https://github.com/your-repo/whisperengine-v2"
        },
        license_info={
            "name": "MIT",
        }
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for now
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(router)

    return app

app = create_app()
