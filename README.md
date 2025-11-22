# WhisperEngine v2

**The "Back to Basics" Production AI Roleplay Platform.**

WhisperEngine v2 is a sophisticated multi-character Discord AI platform designed to create characters that feel alive. It moves beyond simple chatbots by implementing **Long-Term Memory**, **Cognitive Reasoning**, and **Proactive Behavior**.

Built on a "Four Pillars" data architecture, it combines the speed of vector search with the precision of knowledge graphs to deliver deep, evolving roleplay experiences.

## 📚 Architecture & Documentation

WhisperEngine v2 is built on a modular, containerized architecture. We have comprehensive documentation covering every aspect of the system:

### Core Architecture

### 🧠 [The Cognitive Engine](docs/architecture/COGNITIVE_ENGINE.md)
*   **Dual Process Theory**: How the bot switches between "Fast Mode" (System 1) for chat and "Reflective Mode" (System 2) for deep reasoning.
*   **Context Injection**: How personality, memories, and goals are dynamically assembled into the system prompt.

### 🧬 [Memory System v2](docs/architecture/MEMORY_SYSTEM_V2.md)
*   **Human Memory Models**: How Atkinson-Shiffrin and Tulving's theories inform our hybrid memory architecture.
*   **The Living Memory**: Background processes for consolidation, aging, and conflict resolution.
*   **Reasoning Transparency**: Explainable AI through thought traces and source attribution.

### 💾 [Data Models & The "Four Pillars"](docs/architecture/DATA_MODELS.md)
*   **Polyglot Persistence**: Why we use four different databases (Postgres, Qdrant, Neo4j, InfluxDB) instead of one.
*   **Schema Definitions**: Detailed look at vector payloads, graph nodes, and relational tables.

### 🤖 [Discord Integration & Voice](docs/architecture/DISCORD_INTEGRATION.md)
*   **Proactive Agents**: Moving from "Reactive" (Request-Response) to "Proactive" (Event-Driven) behaviors.
*   **Voice Architecture**: How we handle real-time TTS and audio streaming.

### 🏗️ [Infrastructure & Deployment](docs/architecture/INFRASTRUCTURE_DEPLOYMENT.md)
*   **Isolation Patterns**: The "One Container Per Character" strategy for fault tolerance.
*   **Service Mesh**: How the microservices communicate via Docker Compose.

### Design & Implementation

### 📐 [WhisperEngine 2.0 Design Document](docs/architecture/WHISPERENGINE_2_DESIGN.md)
*   **The "Back to Basics" Philosophy**: Simplifying code while sophisticating architecture.
*   **Theoretical Foundations**: Cognitive science, agent theory, and neurosymbolic AI principles.
*   **Technology Stack**: LangChain, Neo4j, and the rationale behind each choice.

### 🔬 [Reflective Mode Implementation](docs/roadmaps/REFLECTIVE_MODE_IMPLEMENTATION.md)
*   **Deep Thinking Architecture**: How the ReAct loop enables complex reasoning.
*   **Production Metrics**: Real-world performance data from deployment.
*   **Cost-Benefit Analysis**: Why the 20x cost increase is justified for 5% of queries.

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

### Start Infrastructure

Start the required databases (PostgreSQL, Qdrant, Neo4j, InfluxDB) using Docker Compose:

```bash
docker compose -f docker-compose.v2.yml up -d
```

### Running the Bot

```bash
python run_v2.py elena
```

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
