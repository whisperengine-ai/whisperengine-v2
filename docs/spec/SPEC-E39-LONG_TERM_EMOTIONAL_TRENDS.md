# SPEC-E39: Long-Term Emotional Trends & Relationship Meta-Summaries

**Status:** 📋 Proposed  
**Phase:** E39 / F-series (Emergent Personhood)  
**Created:** 2025-12-18  
**Complexity:** Medium (new metrics + background job + prompt integration)

---

## Configuration & Feature Flags

```python
# src_v2/config/settings.py

# Phase 1: Enable emotion capture and InfluxDB logging
ENABLE_EMOTIONAL_TREND_TRACKING: bool = True

# Phase 2: Enable meta-summary generation (keep False until data collected)
ENABLE_META_SUMMARIES: bool = False

# Thresholds
META_SUMMARY_MIN_CONVERSATIONS: int = 10  # Minimum conversations to generate summary
```

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Analysis of emergence philosophy + relationship eudaimonia gap |
| **Proposed by** | Mark Castillo (with Claude & Gemini collaboration) |
| **Catalyst** | Question: "Can WhisperEngine track not just what users feel, but long-term trends?" |

---

## Goals

1. **Enable Long-Term Trend Analysis:** Quantify emotional trajectory over months/years
2. **Develop Narrative Self-Model:** Characters auto-generate relationship narratives (autobiographical memory)
3. **Foster Eudaimonic Intelligence:** Allow AI to optimize for long-term meaning, not just hedonic satisfaction
4. **Remain Emergent:** All behaviors emerge from pattern recognition, not hard-coded rules

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Message Flow                              │
└─────────────────────────────────────────────────────────────────┘

User Message
    ↓
[Existing] Conversation Summary + Emotional Detection
    ↓
[NEW] Log sentiment_valence, emotional_intensity to InfluxDB
    ↓
[Existing] Store response to user
    ↓

┌─────────────────────────────────────────────────────────────────┐
│              Weekly Background Job (UTC midnight, Monday)        │
└─────────────────────────────────────────────────────────────────┘

For each [user_id, character_id] pair:
    ↓
1. Query InfluxDB: Last 7 days of emotional metrics
    ↓
2. Compute: Mean valence, intensity, volatility_index
    ↓
3. Query Qdrant: Top 5 key memories from week
    ↓
4. LLM: Generate narrative meta-summary
    ↓
5. Embed: Vector encode the summary
    ↓
6. Store: Save to Qdrant + create Neo4j relationship edge
    ↓
7. Update: Inject into next dynamic prompt

┌─────────────────────────────────────────────────────────────────┐
│          Response Generation (Existing + NEW context)           │
└─────────────────────────────────────────────────────────────────┘

Retrieve context:
  - Recent memories (existing)
  - Knowledge graph facts (existing)
  - [NEW] Latest 2-3 meta-summaries (from Qdrant)
    ↓
Build dynamic prompt with {RELATIONSHIP_EVOLUTION} section
    ↓
Generate response (character implicitly uses trend awareness)
```

---

## Implementation Details

### Phase 1: Emotion Capture & InfluxDB Logging

#### 1.1 Update `SummaryResult` Model

**File:** `src_v2/memory/summarizer.py`

```python
from pydantic import BaseModel, Field

class SummaryResult(BaseModel):
    """Result from conversation summarization."""
    
    summary: str = Field(
        description="Concise summary of the conversation. Include key topics and facts."
    )
    meaningfulness_score: int = Field(
        description="Depth of conversation (1-5). 1=Small talk, 5=Profound sharing.",
        ge=1, le=5
    )
    emotions: List[str] = Field(
        description="List of 2-3 dominant emotions detected (e.g., 'joy', 'anxiety').",
        default_factory=list
    )
    sentiment_valence: float = Field(
        description="Emotional valence (-1.0 to 1.0). -1=Hostile/Sad, 0=Neutral, 1=Joyful/Loving.",
        ge=-1.0, le=1.0
    )
    emotional_intensity: float = Field(
        description="Emotional arousal (0.0 to 1.0). 0=Calm/Bored, 1=Intense/Passionate.",
        ge=0.0, le=1.0
    )
    topics: List[str] = Field(
        description="Key topics or themes (e.g., 'career anxiety', 'creative projects').",
        default_factory=list
    )
```

#### 1.2 Update Summary Agent Prompt

**File:** `src_v2/agents/summary_graph.py`

Update the `build_summary_prompt()` method to instruct LLM:

```python
SUMMARY_SYSTEM_PROMPT = """
You are an expert conversation summarizer for an AI companion system.

RULES:
1. **Ignore filler:** Skip generic greetings ("hi", "bye") unless they are the only content.
2. **Extract facts & opinions:** Focus on what the user cares about, believes, or experienced.
3. **Rate Meaningfulness (1-5):**
   - 1: Small talk, greetings, short jokes
   - 2: Hobbies, daily events, surface interests
   - 3: Personal opinions, preferences, moderate emotional content
   - 4: Deep personal sharing, meaningful experiences, life decisions
   - 5: Trauma, major life transitions, profound philosophical exchange
4. **Detect Emotions:** List 2-3 dominant emotions (joy, anxiety, sadness, curiosity, etc.)
5. **Calculate Sentiment Valence (-1.0 to 1.0):**
   - -1.0: Hostile, deeply sad, hopeless
   - -0.5: Frustrated, worried, somewhat negative
   - 0.0: Neutral, balanced, matter-of-fact
   - 0.5: Optimistic, content, somewhat positive
   - 1.0: Joyful, loving, deeply satisfied
6. **Calculate Emotional Intensity (0.0 to 1.0):**
   - 0.0: Calm, reflective, peaceful
   - 0.5: Engaged, moderately animated
   - 1.0: Passionate, explosive, highly activated

INSTRUCTIONS:
- Output ONLY valid JSON matching the provided schema.
- Do NOT include markdown, code blocks, or conversational text.
- Scores should reflect the overall conversation tone, not isolated moments.
"""
```

#### 1.3 Log Metrics to InfluxDB

**File:** `src_v2/memory/summarizer.py` → `SummaryManager.save_summary()`

```python
async def save_summary(
    self,
    session_id: str,
    user_id: str,
    result: SummaryResult,
    user_name: Optional[str] = None,
    channel_id: Optional[str] = None
) -> bool:
    """Save summary to Postgres, Qdrant, and log metrics to InfluxDB."""
    
    if not db_manager.postgres_pool:
        return False

    try:
        summary_id = str(uuid.uuid4())
        
        # 1. Save to Postgres (existing)
        async with db_manager.postgres_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO v2_summaries 
                (id, session_id, content, meaningfulness_score, emotions)
                VALUES ($1, $2, $3, $4, $5)
            """, 
            summary_id, 
            session_id, 
            result.summary, 
            result.meaningfulness_score,
            json.dumps(result.emotions)
            )
        
        # 2. Log emotional metrics to InfluxDB (NEW)
        if db_manager.influxdb_write_api:
            await self._log_emotional_metrics(
                user_id=user_id,
                result=result,
                session_id=session_id
            )
        
        # 3. Store to Qdrant (existing)
        await self.memory_manager.save_vector_memory(
            user_id=user_id,
            content=result.summary,
            session_id=session_id,
            metadata={"meaningfulness": result.meaningfulness_score}
        )
        
        logger.info(f"Summary saved: {summary_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save summary: {e}")
        raise

@retry_db_operation(max_retries=3)
async def _log_emotional_metrics(
    self,
    user_id: str,
    result: SummaryResult,
    session_id: str
) -> None:
    """Log emotional metrics to InfluxDB for trend analysis."""
    
    from influxdb_client import Point
    from datetime import datetime
    
    try:
        point = Point("user_emotional_state") \
            .tag("user_id", user_id) \
            .tag("bot_name", self.memory_manager.bot_name or "unknown") \
            .tag("session_id", session_id) \
            .field("sentiment_valence", result.sentiment_valence) \
            .field("emotional_intensity", result.emotional_intensity) \
            .field("meaningfulness_score", result.meaningfulness_score) \
            .field("emotions_count", len(result.emotions)) \
            .time(datetime.utcnow())
        
        db_manager.influxdb_write_api.write(
            bucket=settings.INFLUXDB_BUCKET,
            org=settings.INFLUXDB_ORG,
            record=point
        )
        
        logger.info(
            f"Logged emotional metrics for {user_id}: "
            f"V={result.sentiment_valence:.2f}, I={result.emotional_intensity:.2f}"
        )
        
    except Exception as e:
        logger.error(f"Failed to log emotional metrics to InfluxDB: {e}")
        raise
```

---

### Phase 2: Weekly Meta-Summary Generation

#### 2.1 New Background Job

**File:** `src_v2/workers/meta_summary_job.py` (NEW)

```python
"""
Weekly meta-summary generation job.
Runs: UTC midnight every Monday.
Purpose: Synthesize long-term emotional trends into narrative summaries.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
import json
from loguru import logger
from src_v2.core.database import db_manager
from src_v2.memory.manager import memory_manager
from src_v2.agents.llm_factory import llm_factory
from pydantic import BaseModel, Field

class MetaSummaryResult(BaseModel):
    """Structure for relationship meta-summary."""
    
    user_id: str
    character_id: str
    period_start: str  # YYYY-MM-01
    period_end: str    # YYYY-MM-last_day
    summary_narrative: str = Field(
        description="Prose narrative of relationship evolution"
    )
    dominant_emotions: List[str] = Field(
        description="Top 3 emotions over the period"
    )
    valence_trend: str = Field(
        description="Arrow + change (e.g., '↑ +0.15' or '→ stable')"
    )
    intensity_trend: str
    volatility_trend: str
    avg_valence: float
    avg_intensity: float
    avg_meaningfulness: float
    conversation_count: int
    peak_valence: float
    peak_intensity: float
    recommendation: str = Field(
        description="Guidance for character interaction (e.g., 'User responds well to validation-before-advice')"
    )

class MetaSummaryAgent:
    """Generates relationship meta-summaries from emotional data."""
    
    def __init__(self):
        # Use standard LLM factory (reflective model recommended for reasoning)
        self.llm = llm_factory.get_reflective_model()
        self.memory_manager = memory_manager
    
    async def run_weekly_job(self) -> Dict[str, Any]:
        """
        Main entry point. Called weekly via arq worker.
        Returns: Summary of job execution (counts, errors, etc.)
        """
        if not settings.ENABLE_META_SUMMARIES:
            logger.info("Meta-summaries disabled via feature flag")
            return {"status": "disabled"}

        logger.info("Starting weekly meta-summary job")
        
        try:
            # 1. Get all active user-character pairs
            pairs = await self._get_active_pairs()
            logger.info(f"Found {len(pairs)} active pairs")
            
            # 2. Process each pair
            results = {"success": 0, "failed": 0, "errors": []}
            for user_id, char_id in pairs:
                try:
                    await self._generate_and_store_summary(user_id, char_id)
                    results["success"] += 1
                except Exception as e:
                    logger.error(f"Failed to generate summary for {user_id}/{char_id}: {e}")
                    results["failed"] += 1
                    results["errors"].append(str(e))
            
            logger.info(f"Meta-summary job complete. Success: {results['success']}, Failed: {results['failed']}")
            return results
            
        except Exception as e:
            logger.error(f"Meta-summary job failed: {e}")
            raise
    
    async def _get_active_pairs(self) -> List[tuple[str, str]]:
        """Query all user-character pairs with activity in last 7 days."""
        
        query = """
            SELECT DISTINCT user_id, character_id
            FROM v2_trust_scores
            WHERE updated_at > NOW() - INTERVAL '7 days'
            ORDER BY user_id, character_id
        """
        
        async with db_manager.postgres_pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [(row["user_id"], row["character_id"]) for row in rows]
    
    async def _generate_and_store_summary(self, user_id: str, char_id: str) -> None:
        """Generate meta-summary for a user-character pair and store it."""
        
        # 1. Query InfluxDB for metrics
        metrics = await self._fetch_emotional_metrics(user_id, char_id)
        
        # Check threshold
        if metrics["conversation_count"] < settings.META_SUMMARY_MIN_CONVERSATIONS:
            logger.info(f"Insufficient conversations ({metrics['conversation_count']}) for {user_id}/{char_id}, skipping")
            return
        
        # 2. Fetch top memories from Qdrant
        memories = await self._fetch_key_memories(user_id)
        
        # 3. Generate narrative via LLM
        summary = await self._generate_narrative(user_id, char_id, metrics, memories)
        
        # 4. Embed and store to Qdrant
        await self._store_meta_summary(user_id, char_id, summary)
        
        # 5. Update Neo4j relationship edge
        await self._update_graph_relationship(user_id, char_id, summary)
    
    async def _fetch_emotional_metrics(self, user_id: str, char_id: str) -> Dict[str, Any]:
        """Query InfluxDB for user's emotional metrics over last 7 days."""
        
        # Pseudocode: actual implementation uses influxdb_client Flux queries
        # For now: simplified InfluxDB query (actual syntax varies by version)
        
        query = f"""
        from(bucket: "{settings.INFLUXDB_BUCKET}")
            |> range(start: -7d)
            |> filter(fn: (r) => r["_measurement"] == "user_emotional_state")
            |> filter(fn: (r) => r["user_id"] == "{user_id}")
            |> filter(fn: (r) => r["bot_name"] == "{char_id}")
        """
        
        # Query Flux and aggregate
        try:
            tables = db_manager.influxdb_query_api.query_stream(query)
            
            metrics = {
                "valences": [],
                "intensities": [],
                "meaningfulness_scores": [],
                "emotions": [],
                "conversation_count": 0
            }
            
            async for table in tables:
                for record in table.records:
                    if record["_field"] == "sentiment_valence":
                        metrics["valences"].append(record["_value"])
                    elif record["_field"] == "emotional_intensity":
                        metrics["intensities"].append(record["_value"])
                    elif record["_field"] == "meaningfulness_score":
                        metrics["meaningfulness_scores"].append(record["_value"])
            
            # Compute aggregates
            import statistics
            if metrics["valences"]:
                metrics.update({
                    "avg_valence": statistics.mean(metrics["valences"]),
                    "stddev_valence": statistics.stdev(metrics["valences"]) if len(metrics["valences"]) > 1 else 0,
                    "peak_valence": max(metrics["valences"]),
                    "avg_intensity": statistics.mean(metrics["intensities"]),
                    "peak_intensity": max(metrics["intensities"]),
                    "avg_meaningfulness": statistics.mean(metrics["meaningfulness_scores"]),
                    "conversation_count": len(metrics["valences"])
                })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to fetch emotional metrics: {e}")
            return {"conversation_count": 0}
    
    async def _fetch_key_memories(self, user_id: str, limit: int = 5) -> List[str]:
        """Fetch top memories from Qdrant based on significance."""
        
        try:
            results = await self.memory_manager.search_memories(
                user_id=user_id,
                query="relationship development growth",
                top_k=limit,
                min_significance=0.6
            )
            return [r.get("content", "") for r in results if r.get("content")]
        except Exception as e:
            logger.error(f"Failed to fetch memories: {e}")
            return []
    
    async def _generate_narrative(
        self,
        user_id: str,
        char_id: str,
        metrics: Dict[str, Any],
        memories: List[str]
    ) -> MetaSummaryResult:
        """Use LLM to generate narrative meta-summary."""
        
        prompt = f"""
You are analyzing a week of relationship data between an AI character and a user.

METRICS:
- Average sentiment valence: {metrics.get('avg_valence', 0):.2f} (-1=negative, 1=positive)
- Average emotional intensity: {metrics.get('avg_intensity', 0):.2f} (0=calm, 1=intense)
- Conversation count: {metrics.get('conversation_count', 0)}
- Peak valence: {metrics.get('peak_valence', 0):.2f}
- Average conversation depth: {metrics.get('avg_meaningfulness', 3):.1f}/5

KEY MEMORIES FROM THIS WEEK:
{chr(10).join(f"- {m}" for m in memories[:3])}

TASK:
Generate a relationship meta-summary for the character's internal understanding.
This summary will be stored and used to inform future conversations.

OUTPUT JSON with:
- summary_narrative: 3-4 sentences on relationship evolution
- dominant_emotions: List of 3 top emotions observed
- valence_trend: Arrow (↑/→/↓) + change (e.g., "↑ +0.15")
- intensity_trend: Same format
- volatility_trend: Change in emotional variability
- recommendation: 1-2 sentences on effective interaction patterns
"""
        
        response = await self.llm.ainvoke(prompt)
        # Parse JSON from response
        result_dict = json.loads(response.content)
        return MetaSummaryResult(**result_dict)
    
    async def _store_meta_summary(
        self,
        user_id: str,
        char_id: str,
        summary: MetaSummaryResult
    ) -> None:
        """Store meta-summary to Qdrant as long-term memory artifact."""
        
        today = datetime.utcnow().date()
        # Calculate previous week (Monday to Sunday)
        period_end = today - timedelta(days=today.weekday() + 1)
        period_start = period_end - timedelta(days=6)
        
        content = f"""
RELATIONSHIP META-SUMMARY: {user_id} ↔ {char_id}
Period: {period_start} to {period_end}

{summary.summary_narrative}

Emotional Profile:
- Dominant emotions: {', '.join(summary.dominant_emotions)}
- Valence: {summary.avg_valence:.2f} {summary.valence_trend}
- Intensity: {summary.avg_intensity:.2f} {summary.intensity_trend}

Interaction Recommendation:
{summary.recommendation}
"""
        
        meta_id = f"rel_meta_{period_start.strftime('%Y_W%W')}_{user_id}_{char_id}"
        
        # Store to Qdrant
        await self.memory_manager.save_vector_memory(
            user_id=user_id,
            content=content,
            metadata={
                "type": "meta_summary",
                "period_start": str(period_start),
                "period_end": str(period_end),
                "character_id": char_id,
                "significance": 0.9  # High significance
            },
            memory_id=meta_id
        )
        
        logger.info(f"Stored meta-summary: {meta_id}")
    
    async def _update_graph_relationship(
        self,
        user_id: str,
        char_id: str,
        summary: MetaSummaryResult
    ) -> None:
        """Update or create Neo4j relationship edge with evolution data."""
        
        from neo4j import Graph
        
        cypher = """
        MATCH (u:User {id: $user_id})
        MATCH (c:Character {name: $char_id})
        MERGE (u)-[r:RELATIONSHIP_EVOLUTION]->(c)
        SET r.emotional_trend = $emotional_trend,
            r.last_meta_summary_period = $period,
            r.avg_valence = $avg_valence,
            r.avg_intensity = $avg_intensity,
            r.updated_at = datetime()
        """
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                await session.run(
                    cypher,
                    user_id=user_id,
                    char_id=char_id,
                    emotional_trend="positive" if summary.avg_valence > 0.2 else "stable" if summary.avg_valence > -0.2 else "declining",
                    period=datetime.utcnow().date().strftime("%Y-W%W"),
                    avg_valence=summary.avg_valence,
                    avg_intensity=summary.avg_intensity
                )
            logger.info(f"Updated graph relationship: {user_id} → {char_id}")
        except Exception as e:
            logger.error(f"Failed to update graph: {e}")
            raise
```

#### 2.2 Scheduler Setup

**File:** `src_v2/workers/worker.py`

Add to worker initialization (using existing arq scheduler):

```python
# Schedule meta-summary job for Monday at midnight UTC
async def start_background_tasks():
    """Initialize all background jobs."""
    
    # Existing jobs...
    
    # New: Meta-summary job
    from src_v2.workers.meta_summary_job import MetaSummaryAgent
    meta_agent = MetaSummaryAgent()
    
    # Schedule for Monday at 00:00 UTC
    # Note: arq cron syntax
    await task_queue.schedule_cron(
        meta_agent.run_weekly_job,
        cron_string="0 0 * * 1",  # 00:00 on Monday
        unique=True
    )
    
    logger.info("Meta-summary job scheduled")
```

---

### Phase 3: Prompt Integration

#### 3.1 Retrieve Meta-Summaries During Context Building

**File:** `src_v2/agents/router.py` (modify `build_context()`)

```python
async def build_context(
    self,
    user_id: str,
    character: Character,
    message: str,
    chat_history: List[Dict[str, str]]
) -> Dict[str, Any]:
    """Build full context for response generation."""
    
    # Existing context retrieval...
    memories, facts, trust, goals = await asyncio.gather(
        memory_manager.get_recent(user_id),
        knowledge_manager.query_graph(user_id, message),
        trust_manager.get_relationship_level(user_id, character.name),
        goal_manager.get_active_goals(user_id)
    )
    
    # NEW: Fetch latest meta-summaries
    meta_summaries = await self._fetch_meta_summaries(user_id, character.name)
    
    context = {
        "memories": memories,
        "facts": facts,
        "trust": trust,
        "goals": goals,
        "meta_summaries": meta_summaries,  # NEW
        "message": message,
        "chat_history": chat_history
    }
    
    return context

async def _fetch_meta_summaries(
    self,
    user_id: str,
    character_id: str,
    limit: int = 3
) -> List[str]:
    """Fetch latest relationship meta-summaries from Qdrant."""
    
    try:
        results = await memory_manager.search_memories(
            user_id=user_id,
            query=f"relationship evolution {character_id}",
            top_k=limit,
            filters={
                "metadata": {
                    "type": "meta_summary",
                    "character_id": character_id
                }
            }
        )
        return [r.get("content", "") for r in results]
    except Exception as e:
        logger.warning(f"Failed to fetch meta-summaries: {e}")
        return []
```

#### 3.2 Inject into Dynamic Prompt

**File:** `src_v2/agents/engine.py` (modify `generate_response()`)

```python
async def generate_response(
    self,
    user_id: str,
    message: str,
    character: Character,
    chat_history: List[Dict[str, str]]
) -> str:
    """Generate response with full context."""
    
    # Build context (includes meta-summaries)
    context = await self.router.build_context(
        user_id, character, message, chat_history
    )
    
    # Build prompt
    prompt = await self._build_prompt(character, context)
    
    # Generate
    response = await self.llm.ainvoke(prompt)
    return response.content

async def _build_prompt(
    self,
    character: Character,
    context: Dict[str, Any]
) -> str:
    """Build dynamic prompt with relationship context."""
    
    # Existing sections...
    base_prompt = character.system_prompt
    
    # NEW: Add relationship evolution section
    if context.get("meta_summaries"):
        evolution_section = "\n# Relationship Evolution\n"
        for i, summary in enumerate(context["meta_summaries"][:2], 1):
            evolution_section += f"\n--- Week {i} ---\n{summary}\n"
        base_prompt += evolution_section
    
    # Continue with existing sections...
    base_prompt += f"\n# Current Message\n{context['message']}\n"
    
    return base_prompt
```

---
Weekly Job Flow

```
WEEKLY_META_SUMMARY_JOB:

  FOR each active [user_id, character_id] pair:
    
    1. QUERY InfluxDB last 7 days:
       - user_emotional_state measurement
       - Filter: user_id, character_id, time range
       - AGGREGATE: mean, stddev, peak for valence/intensity
       
    2. CALCULATE derived metrics:
       - emotional_volatility_index = stddev(valence_t - valence_t-1)
       - relationship_health_score = (avg_valence + 1) / 2 * avg_meaningfulness / 5
       - trend_direction = slope(linear_regression(timestamps, valences))
       
    3. RETRIEVE top memories:
       - Query Qdrant for user_id
       - Filter: significance > 0.6, created_at > 7 days ago
       - Sort: by significance
       - Take: top 5
       
    4. PROMPT LLM:
       INPUT:
         - Metrics (avg valence, intensity, volatility, conversation count)
         - Top memories (narrative snippets)
         - Period (e.g., "Week 36, 2025")
       
       OUTPUT: MetaSummaryResult JSON with:
         - summary_narrative (3-4 sentences)
         - dominant_emotions (list)
         - valence_trend (e.g., "↑ +0.15")
         - intensity_trend
         - volatility_trend
         - recommendation (for character)
       
    5. STORE to Qdrant:
       - memory_id: "rel_meta_YYYY_WXX_user_id_char_id"
       - content: formatted narrative
       - metadata: {type: "meta_summary", period_start, period_end, significance: 0.9}
       - embedding: auto-generated
       
    6. UPDATE Neo4j:
       - MERGE (user)-[r:RELATIONSHIP_EVOLUTION]->(character)
       - SET r properties: emotional_trend, avg_valence, avg_intensity, updated_at
       
    7. LOG completion

  END FOR
  
  RETURN job summary (success count, failed count, errors)
```

---

## Data Model

### InfluxDB Measurement: `user_emotional_state`

| Tag | Description |
|-----|-------------|
| `user_id` | Discord user ID |
| `bot_name` | Character name |
| `session_id` | Unique conversation session |

| Field | Type | Description |
|-------|------|-------------|
| `sentiment_valence` | float | -1.0 to 1.0 |
| `emotional_intensity` | float | 0.0 to 1.0 |
| `meaningfulness_score` | int | 1 to 5 |
| `emotions_count` | int | Number of emotions detected |

### Neo4j Relationship: `RELATIONSHIP_EVOLUTION`

```
(User)-[r:RELATIONSHIP_EVOLUTION]->(Character)
  Properties:
    - emotional_trend: "positive" | "stable" | "declining" | "volatile"
    - avg_valence: float
    - avg_intensity: float
    - last_meta_summary_period: "2025-W36"
    - updated_at: datetime
```

---

## InfluxDB Query Examples

### Query 1: 7-Day Valence Trend

```flux
from(bucket: "whisperengine")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "user_emotional_state")
  |> filter(fn: (r) => r["user_id"] == "user_123")
  |> filter(fn: (r) => r["_field"] == "sentiment_valence")
  |> aggregateWindow(every: 1d, fn: mean)
```

**Output:** Daily mean valence for 7 days, allowing trend visualization.

### Query 2: Volatility Index (Rolling Std Dev)

```flux
from(bucket: "whisperengine")
  |> range(start: -90d)
  |> filter(fn: (r) => r["_measurement"] == "user_emotional_state" and r["_field"] == "sentiment_valence")
  |> aggregateWindow(every: 7d, fn: stddev)
```

**Output:** Weekly emotional volatility over 90 days.

---

## Testing Strategy

### Unit Tests

1. **Emotion Capture:**
   - Test `SummaryResult` validation with boundary values (-1.0, 0.0, 1.0)
   - Test InfluxDB logging with mock write API

2. **Meta-Summary Generation:**
   - Mock InfluxDB query → Mock metrics → Mock LLM response → Verify JSON structure
   - Test Neo4j relationship creation

3. **Prompt Integration:**
   - Verify meta-summaries appear in dynamic prompt
   - Verify prompt doesn't break with empty meta-summaries

### Integration Tests

1. End-to-end weekly job:
   - Create test conversation data
   - Log metrics to test InfluxDB
   - Run meta-summary job
   - Verify Qdrant storage + Neo4j edges

2. Regression:
   - Existing summary tests still pass
   - Response generation latency unchanged (<100ms)

---

## Observability

### Logs

```python
# During emotion capture
logger.info(f"Logged emotional metrics for {user_id}: V={valence:.2f}, I={intensity:.2f}")

# During meta-summary job
logger.info(f"Fetched metrics for {user_id}/{char_id}: {metrics['conversation_count']} conversations")
logger.info(f"Stored meta-summary: {meta_id}")
logger.info(f"Updated graph relationship: {user_id} → {char_id}")

# Job completion
logger.info(f"Meta-summary job complete. Success: {success}, Failed: {failed}")
```

### Hallucination Safeguards (Phase 2)

To prevent LLMs from inventing narratives not supported by data:

1. **Metric Cross-Check:**
   - If narrative says "deep connection" but `avg_meaningfulness` < 2.5 → Flag for review
   - If narrative says "positive week" but `avg_valence` < 0.0 → Flag for review

2. **Confidence Threshold:**
   - Only generate summaries if `conversation_count` > 10
   - If insufficient data, skip generation (log "insufficient data")

3. **Human Review (First Week):**
   - Log all generated summaries to a review file
   - Manually verify 10-20 samples before enabling prompt injection


### Metrics

- `meta_summary_job_duration_seconds`: How long job takes
- `meta_summary_generation_count`: Summaries generated per run
- `meta_summary_llm_latency_seconds`: LLM response time per summary

### Dashboard (Optional, Phase 2)

Admin-only Grafana dashboard with:
- User emotional valence trends (line chart, 30/90/180 day windows)
- Emotional volatility (area chart)
- Relationship health score (gauge)
- Meta-summary generation job status

---

## Edge Cases & Mitigations

| Case | Risk | Mitigation |
|------|------|-----------|
| User with 0 conversations in week | Empty metrics | Skip generation (log as info, not error) |
| LLM returns invalid JSON | Job fails | Wrap parse in try-catch, fallback to generic summary |
| InfluxDB query timeout | Slow job | Add query timeout (30s), fallback to empty metrics |
| Neo4j connection fails | Graph not updated | Retry with exponential backoff; log warning but continue |
| User deletes all data | Cascade delete | When user data deleted, also delete from InfluxDB (Flux delete) + Qdrant |

---

## Rollout Plan

**Phase 1 (Week 1-2):** Emotion capture + InfluxDB logging
- Update `SummaryResult` + summary agent
- Deploy to elena (dev bot)
- Collect metrics for 7 days (baseline data)

**Phase 2 (Week 3-4):** Meta-summary generation
- Implement background job (disabled by default)
- Enable on elena for validation
- Review generated summaries for hallucination

**Phase 3 (Week 5+):** Prompt integration + trend detection
- Inject meta-summaries into dynamic prompt
- Observe behavior emergence
- Add trend-based proactive features (Phase 2)

---

## References

- **PRD:** [PRD-008-LONG_TERM_EMOTIONAL_TRENDS.md](../prd/PRD-008-LONG_TERM_EMOTIONAL_TRENDS.md)
- **Related SPEC:** [SPEC-E37 (Adaptive Identity)](./SPEC-E37-ADAPTIVE_IDENTITY_SELF_EDITING.md) - E39 provides the emotional signal for E37 evolution
- **Related SPEC:** [SPEC-E12 (Insight Agent)](./SPEC-E12-INSIGHT_AGENT.md)
- **ADR:** [ADR-003 (Emergence Philosophy)](../adr/ADR-003-EMERGENCE_PHILOSOPHY.md)
- **Research:** Eudaimonia vs. Hedonia in `docs/emergence_philosophy/`
