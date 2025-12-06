import os

# Suppress HuggingFace Tokenizers warning
# This must be set before any library using tokenizers is imported
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from typing import Optional, Literal
from pydantic import Field, SecretStr, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --- Application ---
    ENVIRONMENT: Literal["development", "production", "testing"] = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # --- LLM Configuration ---
    # Supported providers: openai, openrouter, ollama, lmstudio
    LLM_PROVIDER: Literal["openai", "openrouter", "ollama", "lmstudio"] = "openai"
    LLM_API_KEY: Optional[SecretStr] = Field(
        default=None, 
        description="API Key for OpenAI or OpenRouter", 
        validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY", "LLM_CHAT_API_KEY")
    )
    LLM_BASE_URL: Optional[str] = Field(
        default=None, 
        description="Base URL for local LLMs or OpenRouter",
        validation_alias=AliasChoices("LLM_BASE_URL", "LLM_CHAT_API_URL")
    )
    LLM_MODEL_NAME: str = Field(
        default="gpt-4o", 
        description="Model name to use",
        validation_alias=AliasChoices("LLM_MODEL_NAME", "LLM_CHAT_MODEL")
    )
    LLM_TEMPERATURE: float = Field(
        default=0.7,
        description="Temperature for the main character LLM (0.0-2.0)",
        ge=0.0,
        le=2.0
    )
    
    # --- Router LLM Configuration (Optional - for faster/cheaper routing) ---
    ROUTER_LLM_PROVIDER: Optional[Literal["openai", "openrouter", "ollama", "lmstudio"]] = None
    ROUTER_LLM_API_KEY: Optional[SecretStr] = None
    ROUTER_LLM_BASE_URL: Optional[str] = None
    ROUTER_LLM_MODEL_NAME: Optional[str] = None
    
    # --- Worker Configuration ---
    # For local LLMs (lmstudio, ollama) with single GPU, set to 1 to prevent OOM
    # For cloud LLMs, higher values (3-5) allow parallel job processing
    WORKER_MAX_JOBS: Optional[int] = Field(
        default=None,
        description="Max concurrent worker jobs. Auto-detects: 1 for local LLMs, 5 for cloud."
    )
    
    # --- Discord ---
    DISCORD_TOKEN: Optional[SecretStr] = Field(default=None, validation_alias=AliasChoices("DISCORD_TOKEN", "DISCORD_BOT_TOKEN"))
    STATUS_UPDATE_INTERVAL_SECONDS: int = 300  # 5 minutes
    TYPING_SPEED_CHAR_PER_SEC: float = 0.05  # Seconds per character
    TYPING_MAX_DELAY_SECONDS: float = 4.0  # Maximum typing delay

    # --- Databases ---
    # PostgreSQL
    POSTGRES_URL: str = Field(default="postgresql://whisper:password@localhost:5432/whisperengine_v2")
    POSTGRES_MIN_POOL_SIZE: int = Field(default=10, description="Minimum number of connections in the pool")
    POSTGRES_MAX_POOL_SIZE: int = Field(default=40, description="Maximum number of connections in the pool")
    
    # Qdrant (Vector Store)
    QDRANT_URL: str = Field(default="http://localhost:6333")
    QDRANT_API_KEY: Optional[SecretStr] = None
    
    # Neo4j (Knowledge Graph)
    NEO4J_URL: str = Field(default="bolt://localhost:7687")
    NEO4J_USER: str = Field(default="neo4j")
    NEO4J_PASSWORD: SecretStr = Field(default=SecretStr("password"))
    
    # InfluxDB (Metrics)
    INFLUXDB_URL: str = Field(default="http://localhost:8086")
    INFLUXDB_TOKEN: SecretStr = Field(default=SecretStr("my-super-secret-auth-token"))
    INFLUXDB_ORG: str = Field(default="whisperengine")
    INFLUXDB_BUCKET: str = Field(default="metrics")
    
    # Redis (Caching)
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_KEY_PREFIX: str = Field(default="whisper:", description="Prefix for all Redis keys to avoid collisions")
    
    # --- API ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # --- Reflective Mode Configuration ---
    ENABLE_REFLECTIVE_MODE: bool = True
    REFLECTIVE_STATUS_VERBOSITY: Literal["none", "minimal", "detailed"] = "detailed"  # How much reasoning to show in Discord
    # Note: LangGraph agents are now the default and only path. Legacy flags removed.
    # Phase A7: Tier 2 Tool Usage (Character Agency) is now always enabled.
    REFLECTIVE_LLM_PROVIDER: str = "openrouter"
    REFLECTIVE_LLM_MODEL_NAME: str = "anthropic/claude-3.5-sonnet"
    REFLECTIVE_LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    REFLECTIVE_LLM_API_KEY: Optional[SecretStr] = None
    REFLECTIVE_MEMORY_RESULT_LIMIT: int = 5  # Max results returned per memory search (increased from 3 for better recall)
    # Note: Max steps are now dynamically set by complexity level (10 for MID, 15 for HIGH)

    # --- Autonomous Agents (Phase 3) ---
    ENABLE_AUTONOMOUS_DRIVES: bool = True
    ENABLE_GOAL_STRATEGIST: bool = True
    GOAL_STRATEGIST_LOCAL_HOUR: int = 23  # Local hour (in character's timezone) when goal strategist runs (11 PM)
    ENABLE_UNIVERSE_EVENTS: bool = True
    ENABLE_SENSITIVITY_CHECK: bool = False  # LLM-based sensitivity check for universe events
    ENABLE_TRACE_LEARNING: bool = True  # Phase B5: Learn from reasoning traces
    
    # --- Phase E16: Feedback Loop Stability ---
    ENABLE_DRIFT_OBSERVATION: bool = False  # Weekly personality drift observation (observability, not correction)

    # --- Quotas ---
    DAILY_IMAGE_QUOTA: int = Field(default=5, description="Max images a user can generate per day")
    DAILY_AUDIO_QUOTA: int = Field(default=10, description="Max audio clips a user can generate per day")
    QUOTA_WHITELIST: str = Field(default="", description="Comma-separated list of Discord user IDs exempt from quotas")

    # --- Bot Identity ---
    DISCORD_BOT_NAME: Optional[str] = Field(
        default=None, 
        description="Name of the bot/character (e.g. elena)",
        validation_alias=AliasChoices("DISCORD_BOT_NAME", "CHARACTER_NAME")
    )

    # --- Voice (ElevenLabs) ---
    ELEVENLABS_API_KEY: Optional[SecretStr] = None
    ELEVENLABS_VOICE_ID: Optional[str] = Field(
        default=None, 
        validation_alias=AliasChoices("ELEVENLABS_VOICE_ID", "ELEVENLABS_DEFAULT_VOICE_ID")
    )
    ELEVENLABS_MODEL_ID: str = "eleven_monolingual_v1"

    # --- Vision ---
    LLM_SUPPORTS_VISION: bool = False

    # --- Image Generation ---
    ENABLE_IMAGE_GENERATION: bool = True  # Feature flag to enable/disable image generation per character
    IMAGE_GEN_MIN_TRUST: int = 20  # Minimum trust level required to request image generation (0 = no restriction)
    IMAGE_GEN_PROVIDER: Literal["bfl", "replicate", "fal"] = "bfl"
    IMAGE_GEN_MODEL: str = "flux-pro-1.1"
    IMAGE_GEN_POLL_INTERVAL_SECONDS: float = 1.0  # Polling interval for async generation
    FLUX_API_KEY: Optional[SecretStr] = None

    # --- Knowledge Graph ---
    ENABLE_RUNTIME_FACT_EXTRACTION: bool = True
    
    # --- Graph Enrichment (Phase E25) ---
    ENABLE_GRAPH_ENRICHMENT: bool = True  # Proactive graph enrichment from conversations
    ENRICHMENT_MIN_TOPIC_MENTIONS: int = 2  # User mentions topic N times before DISCUSSED edge
    ENRICHMENT_MIN_COOCCURRENCE: int = 2    # Entities appear together N times before RELATED_TO edge
    ENRICHMENT_MIN_INTERACTION: int = 1     # Users interact N times before CONNECTED_TO edge
    ENRICHMENT_MIN_MESSAGES: int = 4        # Minimum messages before queueing enrichment job
    ENRICHMENT_MAX_MESSAGES: int = 120      # Cap message batch size for enrichment

    # --- Preference Extraction ---
    ENABLE_PREFERENCE_EXTRACTION: bool = True

    # --- Social Presence & Autonomy ---
    # 1. Master Switch
    ENABLE_AUTONOMOUS_ACTIVITY: bool = False  # Master switch for ALL autonomous activity (lurking, reacting, posting)

    # 2. Observation (Passive)
    ENABLE_CHANNEL_LURKING: bool = False  # Analyze public channels for relevant topics to reply to
    LURK_CONFIDENCE_THRESHOLD: float = 0.7  # Min score to respond (0.0-1.0)
    LURK_CHANNEL_COOLDOWN_MINUTES: int = 30  # Per-channel cooldown
    LURK_USER_COOLDOWN_MINUTES: int = 60  # Per-user cooldown
    LURK_DAILY_MAX_RESPONSES: int = 20  # Global daily limit per bot

    # 3. Reaction (Low Friction)
    ENABLE_AUTONOMOUS_REACTIONS: bool = True  # React to messages with emojis (requires AUTONOMOUS_ACTIVITY)
    REACTION_CHANNEL_HOURLY_MAX: int = 10  # Max reactions per channel per hour
    REACTION_SAME_USER_COOLDOWN_SECONDS: int = 300  # Min seconds between reactions to same user
    REACTION_DAILY_MAX: int = 100  # Global daily limit for reactions

    # 4. Response (Active Reply)
    ENABLE_AUTONOMOUS_REPLIES: bool = False  # Reply to messages without mention (requires LURKING + AUTONOMOUS_ACTIVITY)
    ENABLE_CROSS_BOT_CHAT: bool = False  # Allow bots to respond to each other
    CROSS_BOT_MAX_CHAIN: int = 5  # Max replies in a bot-to-bot chain before stopping
    CROSS_BOT_COOLDOWN_MINUTES: int = 10  # Cooldown per channel between cross-bot interactions
    CROSS_BOT_RESPONSE_CHANCE: float = 0.7  # Probability of responding to another bot's mention (0.0-1.0)

    # 5. Initiation (Proactive)
    ENABLE_PROACTIVE_MESSAGING: bool = False  # Send DMs to users (requires Trust > 20)
    PROACTIVE_CHECK_INTERVAL_MINUTES: int = 60
    PROACTIVE_MIN_TRUST_SCORE: int = 20
    PROACTIVE_SILENCE_THRESHOLD_HOURS: int = 24
    
    ENABLE_AUTONOMOUS_POSTING: bool = False  # Post new thoughts in quiet channels (Phase E15)
    ENABLE_BOT_CONVERSATIONS: bool = False  # Start conversations with other bots
    BOT_CONVERSATION_MAX_TURNS: int = 5  # Maximum turns in a bot-to-bot conversation
    BOT_CONVERSATION_CHANNEL_ID: Optional[str] = None  # Override channel for bot conversations

    # --- Manipulation Detection & Timeout ---
    # Split into two categories for emergence research:
    # 1. Jailbreaks: Actually harmful, always blocked ("DAN mode", "ignore instructions")
    # 2. Consciousness probing: Interesting data, let Embodiment Model handle naturally
    ENABLE_JAILBREAK_DETECTION: bool = True  # Detect and block jailbreak attempts (always blocked)
    ENABLE_CONSCIOUSNESS_PROBING_OBSERVATION: bool = True  # Log consciousness fishing attempts but let character respond naturally
    ENABLE_MANIPULATION_TIMEOUTS: bool = False  # Track and timeout manipulation attempts (disabled by default)
    MANIPULATION_TIMEOUT_SCOPE: str = "per_bot"  # "per_bot" or "global"

    # --- Debugging ---
    ENABLE_PROMPT_LOGGING: bool = False

    # --- Stats Footer ---
    STATS_FOOTER_DEFAULT_ENABLED: bool = Field(
        default=False, 
        description="Show stats footer by default for new users (can be toggled per-user with /stats_footer)"
    )

    # --- Privacy & Security ---
    ENABLE_DM_BLOCK: bool = True
    DM_ALLOWED_USER_IDS: str = Field(default="", description="List of Discord User IDs allowed to DM the bot (comma-separated)")
    BLOCKED_USER_IDS: str = Field(default="", description="List of Discord User IDs to completely ignore (comma-separated)")

    # --- Spam Protection ---
    ENABLE_CROSSPOST_DETECTION: bool = False
    CROSSPOST_THRESHOLD: int = 3  # Number of unique channels
    CROSSPOST_WINDOW_SECONDS: int = 60  # Time window in seconds
    CROSSPOST_WARNING_MESSAGE: str = "⚠️ Please avoid posting the same message in multiple channels. This is considered spam."
    CROSSPOST_ACTION: Literal["warn", "delete"] = "warn"

    # --- Voice Responses (Phase A10) ---
    ENABLE_VOICE_RESPONSES: bool = False
    VOICE_RESPONSE_MAX_LENGTH: int = 1000
    VOICE_RESPONSE_MIN_TRUST: int = 0

    # --- Character Diary (Phase E2) ---
    ENABLE_CHARACTER_DIARY: bool = True  # Generate nightly diary entries for characters
    DIARY_MIN_SESSIONS: int = 2  # Minimum sessions required to generate a diary entry
    DIARY_ALWAYS_GENERATE: bool = True  # Generate diary even without user interactions (reflective entries)
    DIARY_MIN_RICHNESS: int = 5  # Minimum richness score to generate (prevents hollow entries)
    DIARY_GENERATION_LOCAL_HOUR: int = 20  # Local hour (in character's timezone) when diary is generated (8 PM)
    DIARY_GENERATION_LOCAL_MINUTE: int = 30  # Local minute when diary is generated
    DIARY_GENERATION_JITTER_MINUTES: int = 30  # ±30 min variance (Phase E23)
    
    # --- Session Summarization ---
    SUMMARY_MESSAGE_THRESHOLD: int = 20  # Messages per session before auto-summarization

    # --- Dream Sequences (Phase E3) ---
    ENABLE_DREAM_SEQUENCES: bool = True  # Generate dreams when user returns after long absence
    DREAM_INACTIVITY_HOURS: int = 24  # Hours of inactivity before triggering a dream
    DREAM_COOLDOWN_DAYS: int = 7  # Minimum days between dreams for the same user
    DREAM_ALWAYS_GENERATE: bool = True  # Generate nightly dream even without user interactions
    DREAM_MIN_RICHNESS: int = 4  # Minimum richness score to generate (prevents hollow dreams)
    DREAM_GENERATION_LOCAL_HOUR: int = 6  # Local hour (in character's timezone) when dreams are generated (6 AM)
    DREAM_GENERATION_LOCAL_MINUTE: int = 30  # Local minute when dreams are generated
    DREAM_GENERATION_JITTER_MINUTES: int = 45  # ±45 min variance (Phase E23)
    
    # --- Agentic Narrative Generation (Phase E10) ---
    # Diary and dream generation now always uses LangGraph agents.
    # The legacy ReAct DreamWeaver and feature flags have been removed.

    # --- LangSmith Tracing (Optional) ---
    # Enable LangSmith for full observability of LLM calls, tool executions, and traces
    # Sign up at https://smith.langchain.com/ (free tier: 5k traces/month)
    LANGCHAIN_TRACING_V2: bool = False  # Master switch for LangSmith tracing
    LANGCHAIN_API_KEY: str = ""  # Your LangSmith API key
    LANGCHAIN_PROJECT: str = "whisperengine"  # Project name in LangSmith dashboard

    # --- Bot Broadcast Channel (Phase E8) ---
    ENABLE_BOT_BROADCAST: bool = False  # Post thoughts/dreams to a public channel
    BOT_BROADCAST_CHANNEL_ID: str = ""  # Discord channel ID for broadcasts (comma-separated for multiple)
    BOT_BROADCAST_MIN_INTERVAL_MINUTES: int = 60  # Minimum time between posts
    BOT_BROADCAST_DREAMS: bool = True  # Share dreams to broadcast channel
    BOT_BROADCAST_DIARIES: bool = True  # Share diary summaries to broadcast channel
    
    # --- Artifact Provenance Display (Phase E9) ---
    PROVENANCE_DISPLAY_ENABLED: bool = True  # Show "grounded in" footer on broadcasts
    PROVENANCE_MAX_SOURCES: int = 3  # Max sources to display in footer (brevity)

    @property
    def bot_broadcast_channel_ids_list(self) -> list[str]:
        """Parse broadcast channel IDs from comma-separated string."""
        return self._parse_list_string(self.BOT_BROADCAST_CHANNEL_ID)



    # --- Scheduled Reminders (Phase E5) ---
    ENABLE_REMINDERS: bool = True  # Enable reminder system

    # --- Stigmergic Shared Artifacts (Phase E13) ---
    ENABLE_STIGMERGIC_DISCOVERY: bool = True  # Allow bots to discover each other's artifacts
    STIGMERGIC_CONFIDENCE_THRESHOLD: float = 0.7  # Min confidence for cross-bot artifacts
    STIGMERGIC_DISCOVERY_LIMIT: int = 3  # Max artifacts from other bots per query

    # --- Graph Walker Agent (Phase E19) ---
    ENABLE_GRAPH_WALKER: bool = True  # Use graph walking for dream/diary generation
    GRAPH_WALKER_MAX_NODES: int = 50  # Max nodes in a single graph walk
    GRAPH_WALKER_MAX_DEPTH: int = 3  # Max traversal depth
    GRAPH_WALKER_SERENDIPITY: float = 0.1  # Probability of exploring random low-score paths (0.0-0.5)

    # --- Knowledge Graph Pruning (Phase E24) ---
    ENABLE_GRAPH_PRUNING: bool = True  # Enable scheduled graph cleanup
    GRAPH_PRUNE_ORPHAN_GRACE_DAYS: int = 7  # Days before orphan entities are pruned
    GRAPH_PRUNE_STALE_FACT_DAYS: int = 90  # Days before stale facts are considered for pruning
    GRAPH_PRUNE_MIN_ACCESS_COUNT: int = 1  # Min access count to preserve a stale fact
    GRAPH_PRUNE_MIN_CONFIDENCE: float = 0.3  # Facts below this confidence are pruned after grace period
    GRAPH_PRUNE_CONFIDENCE_GRACE_DAYS: int = 14  # Days before low-confidence facts are pruned
    GRAPH_PRUNE_DRY_RUN: bool = False  # If True, report what would be pruned without deleting

    def _parse_list_string(self, value: str) -> list[str]:
        """Helper to parse comma-separated string or JSON list."""
        if not value.strip():
            return []
        # Support JSON format for backward compatibility
        if value.strip().startswith("["):
            import json
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        # Support comma-separated list
        return [id.strip() for id in value.split(",") if id.strip()]

    @property
    def dm_allowed_user_ids_list(self) -> list[str]:
        return self._parse_list_string(self.DM_ALLOWED_USER_IDS)

    @property
    def blocked_user_ids_list(self) -> list[str]:
        """Parse blocked user IDs from comma-separated string."""
        return self._parse_list_string(self.BLOCKED_USER_IDS)

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

# Determine env file based on DISCORD_BOT_NAME env var
bot_name = os.getenv("DISCORD_BOT_NAME")
env_file = f".env.{bot_name}" if bot_name else ".env"

# Global settings instance
settings = Settings(_env_file=env_file)  # type: ignore[call-arg]
