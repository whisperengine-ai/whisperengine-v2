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
from src_v2.api.routes import router


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
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
