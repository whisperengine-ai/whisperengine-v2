# WhisperEngine v2 - New Repository Setup

## Repository Information

- **Location**: `/Users/markcastillo/git/whisperengine-v2`
- **Branch**: `whisperengine-2.0-init`
- **Remote**: Not yet configured (local only)

## Structure

The new repository includes all v2-specific code and supporting files:

### Core Directories

- **`src_v2/`** - Complete v2 codebase
  - `agents/` - LLM routing and generation
  - `core/` - Database connections and character loading
  - `discord/` - Discord bot integration
  - `evolution/` - Goal tracking, trust management, feedback
  - `knowledge/` - Neo4j graph management
  - `memory/` - Vector and chat history storage
  - `utils/` - Utilities and helpers

- **`characters/`** - Character definitions
  - `elena/` - Character files and goals
  - `goals.yaml.template` - Template for new characters

- **`alembic/`** - Database schema migrations
  - `versions/` - All migration files
  - `env.py` - Migration configuration

- **`tests/`** - Test suite
- **`docs/`** - Architecture and roadmap documentation
- **`scripts/`** - Utility scripts

### Key Files

- **`run_v2.py`** - Entry point for running characters
- **`requirements.txt`** - Python dependencies (includes PyYAML)
- **`alembic.ini`** - Alembic configuration
- **`.env.example`** - Environment template

## Recent Changes

1. Added comprehensive `.gitignore`
2. Updated `README.md` with v2-specific documentation
3. Created new repository with `whisperengine-2.0-init` as main branch

## Next Steps

### Option 1: Push to GitHub (Recommended)

```bash
cd /Users/markcastillo/git/whisperengine-v2

# Add GitHub remote
git remote add origin https://github.com/whisperengine-ai/whisperengine-v2.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Option 2: Keep Local

The repository is ready to use locally:

```bash
cd /Users/markcastillo/git/whisperengine-v2
python run_v2.py elena
```

## Development Workflow

1. **Database Setup**: Run Alembic migrations
   ```bash
   alembic upgrade head
   ```

2. **Environment Configuration**: Create `.env.charactername`
   ```bash
   cp .env.example .env.elena
   ```

3. **Run Character Bot**:
   ```bash
   python run_v2.py elena
   ```

4. **Add New Character**:
   ```bash
   mkdir -p characters/newcharacter
   cp characters/elena/character.md characters/newcharacter/
   cp characters/goals.yaml.template characters/newcharacter/goals.yaml
   cp .env.example .env.newcharacter
   ```

## Key Features

- **Character-Agnostic Codebase**: All character data loaded from external files
- **Goal System**: YAML-based character goals with database tracking
- **Vector Memory**: Qdrant with 384D embeddings
- **Knowledge Graph**: Neo4j for user facts and relationships
- **Multi-Character Support**: Run multiple characters simultaneously
- **API Server**: FastAPI on port 8000 for HTTP chat endpoints

## Notes

- Original repo: `/Users/markcastillo/git/whisperengine`
- V1 code remains in original repository on different branches
- This repository is purely WhisperEngine v2
- All secrets in `.env.*` files are ignored (per `.gitignore`)
