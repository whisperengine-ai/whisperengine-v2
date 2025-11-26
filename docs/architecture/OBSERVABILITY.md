# Observability & Metrics

WhisperEngine v2 uses InfluxDB for time-series metrics and Grafana for visualization.

## Metrics Schema

### 1. Response Metrics (`response_metrics`)
Tracks the performance and characteristics of the AI response generation.
- **Tags**:
  - `user_id`: Discord User ID
  - `bot_name`: Character name (e.g., "elena")
  - `mode`: "fast" (direct LLM) or "reflective" (ReAct loop)
  - `complexity`: "simple", "COMPLEX_LOW", "COMPLEX_MID", "COMPLEX_HIGH"
- **Fields**:
  - `latency`: Total response time in seconds (float)

### 2. Trust Updates (`trust_update`)
Tracks changes in the relationship trust score.
- **Tags**:
  - `user_id`: Discord User ID
  - `bot_name`: Character name
- **Fields**:
  - `trust_score`: New absolute trust score (-100 to 100)
  - `delta`: Change amount (e.g., +5, -2)

### 3. Tool Usage (`tool_usage`)
Tracks which cognitive tools are called by the Router.
- **Tags**:
  - `tool_name`: Name of the tool (e.g., "search_memories", "lookup_facts")
  - `user_id`: Discord User ID
  - `bot_name`: Character name
- **Fields**:
  - `duration_ms`: Execution time in milliseconds
  - `success`: Boolean (true/false)

### 4. Memory Latency (`memory_latency`)
Tracks performance of the Vector Database (Qdrant).
- **Tags**:
  - `user_id`: Discord User ID
  - `operation`: "read" (search) or "write" (upsert)
- **Fields**:
  - `duration_ms`: Execution time in milliseconds
  - `result_count`: Number of memories found (read only)

### 5. Knowledge Latency (`knowledge_latency`)
Tracks performance of the Graph Database (Neo4j).
- **Tags**:
  - `user_id`: Discord User ID
  - `type`: "query" (natural language) or "default" (recent facts)
- **Fields**:
  - `duration_ms`: Execution time in milliseconds
  - `result_count`: Number of facts retrieved

### 6. User Reactions (`reaction_event`)
Tracks user emoji reactions to bot messages.
- **Tags**:
  - `user_id`: Discord User ID
  - `bot_name`: Character name
  - `message_id`: Discord Message ID
  - `action`: "add" or "remove"
- **Fields**:
  - `reaction`: The emoji string
  - `message_length`: Length of the message reacted to

### 7. Message Events (`message_event`)
Tracks incoming user messages.
- **Tags**:
  - `user_id`: Discord User ID
  - `bot_name`: Character name
  - `channel_type`: "dm" or "guild"
- **Fields**:
  - `length`: Character count of the message

## Grafana Dashboards

Dashboards are provisioned automatically from `docker/grafana/dashboards/`.
- **WhisperEngine Overview**: High-level stats on latency, trust, and engagement.
