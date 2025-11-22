# WhisperEngine v2 AI Agent Instructions

**WhisperEngine v2 is a production multi-character Discord AI roleplay platform.**
It uses a sophisticated architecture with Vector Memory (Qdrant), Knowledge Graphs (Neo4j), and Character Definition Language (CDL).

## 📋 Documentation & Security Philosophy

- **No Undocumented Files**: Do not create `.md`, `.txt`, or doc files without explicit user approval. Code is the source of truth.
- **No Secrets in Git**: Never commit `.env` files. Use `.env.example` for templates.
- **Ask Before Restarting**: In production contexts, ask before restarting services. In development, use your judgment but prefer hot-reloading where possible (though Python code changes often require restarts).

## 🏗️ Architecture & Core Components

### **Entry Point & Runtime**
- **Entry**: `run_v2.py <bot_name>` is the single entry point. It sets `DISCORD_BOT_NAME` and loads `src_v2.main`.
- **App Structure**: `src_v2/main.py` initializes:
  - **Database Manager**: `src_v2/core/database.py` (Postgres)
  - **Memory System**: `src_v2/memory/manager.py` (Qdrant)
  - **Knowledge Graph**: `src_v2/knowledge/manager.py` (Neo4j)
  - **Discord Bot**: `src_v2/discord/bot.py` (Discord.py)
  - **API Server**: `src_v2/api/app.py` (FastAPI)

### **Data Layer (The "Four Pillars")**
1.  **PostgreSQL** (Port 5432): Relational data, CDL storage, user preferences.
2.  **Qdrant** (Port 6333): Vector memory (384D embeddings) for semantic conversation retrieval.
3.  **Neo4j** (Port 7687): Knowledge graph for entity relationships and facts.
4.  **InfluxDB** (Port 8086): Time-series metrics for engagement and performance.

## 🚀 Critical Workflows

### **Running the Application**
```bash
# Start Infrastructure
docker compose -f docker-compose.v2.yml up -d

# Run a specific character (loads .env.elena)
source .venv/bin/activate
python run_v2.py elena
```

### **Testing & Validation**
- **Direct Python Validation (Preferred)**:
  ```bash
  source .venv/bin/activate
  python tests/automated/test_feature_direct_validation.py
  ```
- **HTTP API Testing**:
  POST to `http://localhost:8000/api/chat` with JSON payload.

### **Database Migrations**
- Uses **Alembic** for PostgreSQL schema changes.
- **Ensure .venv is activated**: `source .venv/bin/activate`
- **Create**: `alembic revision --autogenerate -m "description"`
- **Apply**: `alembic upgrade head`
- **Location**: `migrations_v2/` (Do not use `migrations/` from v1).

## ⚙️ Configuration & Environment

- **Settings**: Managed via Pydantic in `src_v2/config/settings.py`.
- **Env Files**:
  - `run_v2.py` automatically selects `.env.{bot_name}` based on the argument.
  - Fallback to `.env` if no argument provided.
- **Critical Var**: `DISCORD_BOT_NAME` drives character loading and config selection.

## 🧩 Character System

- **Location**: `characters/{name}/`
- **Files**:
  - `character.md`: Personality, backstory, and traits.
  - `goals.yaml`: Evolution goals and learning objectives.
- **Adding a Character**: Copy `characters/elena/` structure and create `.env.{new_name}`.

## 📝 Coding Standards & Patterns

- **Async First**: Use `async/await` for all I/O (DB, API, Discord).
- **Logging**: Use `loguru` (`from loguru import logger`), not standard `logging`.
- **Type Safety**: Use Pydantic models for data validation and settings.
- **Path Handling**: Use `pathlib.Path` over `os.path`.
- **Tokenizers**: `os.environ["TOKENIZERS_PARALLELISM"] = "false"` is set in `run_v2.py` to prevent warnings.

## ⚠️ Common Pitfalls

- **Do NOT use `multi-bot.sh`**: This is a v1 legacy script. Use `run_v2.py`.
- **Do NOT edit `src/`**: Work only in `src_v2/`.
- **Do NOT commit `.env` files**: They contain secrets.
- **Restarting**: Python code changes require restarting the `run_v2.py` process (no hot-reload for bot logic).
