# WhisperEngine v2

A production multi-character Discord AI roleplay platform with vector-native memory, Neo4j knowledge graphs, and character-driven personality systems.

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 16+
- Qdrant vector database
- Neo4j graph database
- InfluxDB time-series database
- Discord bot token

### Installation

```bash
# Clone the repository
git clone https://github.com/whisperengine-ai/whisperengine-v2.git
cd whisperengine-v2

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env.elena
# Edit .env.elena with your configuration
```

### Running the Bot

```bash
python run_v2.py elena
```

## Architecture

### Core Systems

- **Vector Memory**: Qdrant with 384D embeddings for semantic conversation retrieval
- **Knowledge Graph**: Neo4j for user facts, relationships, and entity management
- **Character System**: PostgreSQL-driven CDL (Character Definition Language)
- **Evolution System**: Goal tracking, trust management, and behavioral adaptation
- **API Server**: FastAPI on port 8000 for health checks and chat endpoints

## Character Configuration

Each character has:
- `characters/{name}/character.md` - Personality and metadata
- `characters/{name}/goals.yaml` - Character-specific goals and learning objectives

### Adding a New Character

1. Create directory: `characters/newcharacter/`
2. Copy character definition: `cp characters/elena/character.md characters/newcharacter/`
3. Copy goals template: `cp characters/goals.yaml.template characters/newcharacter/goals.yaml`
4. Edit both files with character specifics
5. Create environment file: `.env.newcharacter`

## Development

### Database Migrations

Alembic handles schema changes:

```bash
# Create a migration
alembic revision --autogenerate -m "migration description"

# Apply migrations
alembic upgrade head
```

### Testing

```bash
# Run direct Python validation (preferred)
source .venv/bin/activate
python tests/automated/test_feature_direct_validation.py

# Test via HTTP API
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_123",
    "message": "Hello!",
    "metadata": {"platform": "api_test"}
  }'
```

## Documentation

- `docs/` - Architecture and design documentation
- `docs/roadmaps/` - Development roadmaps and feature planning

## License

See LICENSE file for details.
