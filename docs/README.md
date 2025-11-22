# WhisperEngine v2 Documentation

Welcome to the WhisperEngine v2 documentation! This directory contains everything you need to understand, deploy, and develop WhisperEngine v2.

## Quick Navigation

### Getting Started
- **[Installation](./INSTALLATION.md)** - Set up WhisperEngine v2 locally
- **[Quick Start](./QUICK_START.md)** - Run your first character bot
- **[Configuration](./CONFIGURATION.md)** - Environment setup and customization

### Architecture & Design
- **[System Architecture](./ARCHITECTURE.md)** - Overview of core systems
- **[Database Schema](./DATABASE.md)** - PostgreSQL, Qdrant, and Neo4j setup
- **[Memory System](./MEMORY.md)** - Vector memory and chat history

### Development
- **[Development Guide](./DEVELOPMENT.md)** - Setting up for development
- **[Testing](./TESTING.md)** - Running tests
- **[API Reference](./API.md)** - HTTP endpoints

### Deployment
- **[Docker Setup](./DOCKER.md)** - Containerization guide
- **[Production](./PRODUCTION.md)** - Deployment best practices
- **[Scaling](./SCALING.md)** - Multi-character setup

### Character System
- **[Character Guide](./CHARACTERS.md)** - Creating and configuring characters
- **[Goals System](./GOALS.md)** - Character learning objectives
- **[Evolution System](./EVOLUTION.md)** - Trust and goal tracking

## Directory Structure

```
docs/
├── README.md              # This file
├── INSTALLATION.md        # Setup guide
├── QUICK_START.md         # First steps
├── ARCHITECTURE.md        # System design
├── DATABASE.md            # Schema documentation
├── MEMORY.md              # Memory systems
├── CHARACTERS.md          # Character creation
├── GOALS.md               # Goals management
├── EVOLUTION.md           # Evolution system
├── API.md                 # API documentation
├── TESTING.md             # Testing guide
├── DEVELOPMENT.md         # Dev guide
├── DOCKER.md              # Container guide
├── PRODUCTION.md          # Production setup
└── SCALING.md             # Scaling guide
```

## Key Features

- **Multi-Character Support** - Run 10+ independent AI characters simultaneously
- **Vector Memory** - Semantic conversation retrieval with Qdrant (384D embeddings)
- **Knowledge Graph** - Neo4j for user facts and relationships
- **Evolution System** - Character learning and goal tracking
- **Discord Integration** - Native Discord bot with full event pipeline
- **HTTP API** - RESTful chat endpoints for automation

## Support

For issues or questions, refer to:
1. **This documentation** - Most common questions answered here
2. **Source code** - Well-commented code in `src_v2/`
3. **Tests** - Example usage in `tests/` and `tests_v2/`

## Version

**WhisperEngine v2** - Latest: November 2025
