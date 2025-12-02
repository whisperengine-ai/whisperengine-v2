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
    ENABLE_REFLECTIVE_MODE: bool = False
    REFLECTIVE_STATUS_VERBOSITY: Literal["none", "minimal", "detailed"] = "detailed"  # How much reasoning to show in Discord
    ENABLE_LANGGRAPH_REFLECTIVE_AGENT: bool = False  # Enable new LangGraph-based reflective agent
    ENABLE_LANGGRAPH_CHARACTER_AGENT: bool = False  # Enable new LangGraph-based character agent
    ENABLE_LANGGRAPH_INSIGHT_AGENT: bool = False  # Enable new LangGraph-based insight agent
    ENABLE_LANGGRAPH_DIARY_AGENT: bool = False  # Enable new LangGraph-based diary agent
    ENABLE_LANGGRAPH_DREAM_AGENT: bool = False  # Enable new LangGraph-based dream agent
    ENABLE_LANGGRAPH_REFLECTION_AGENT: bool = False  # Enable new LangGraph-based reflection agent
    ENABLE_LANGGRAPH_STRATEGIST_AGENT: bool = False  # Enable new LangGraph-based goal strategist agent
    ENABLE_SUPERGRAPH: bool = False  # Enable Master Supergraph architecture
    ENABLE_CHARACTER_AGENCY: bool = True  # Phase A7: Tier 2 Tool Usage
    REFLECTIVE_LLM_PROVIDER: str = "openrouter"
    REFLECTIVE_LLM_MODEL_NAME: str = "anthropic/claude-3.5-sonnet"
    REFLECTIVE_LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    REFLECTIVE_LLM_API_KEY: Optional[SecretStr] = None
    REFLECTIVE_MEMORY_RESULT_LIMIT: int = 3  # Max results returned per memory search
    # Note: Max steps are now dynamically set by complexity level (10 for MID, 15 for HIGH)

    # --- Autonomous Agents (Phase 3) ---
    ENABLE_AUTONOMOUS_DRIVES: bool = False
    ENABLE_GOAL_STRATEGIST: bool = False
    GOAL_STRATEGIST_LOCAL_HOUR: int = 23  # Local hour (in character's timezone) when goal strategist runs (11 PM)
    ENABLE_UNIVERSE_EVENTS: bool = False
    ENABLE_SENSITIVITY_CHECK: bool = False  # LLM-based sensitivity check for universe events
    ENABLE_TRACE_LEARNING: bool = False
    
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

    # --- Preference Extraction ---
    ENABLE_PREFERENCE_EXTRACTION: bool = True

    # --- Proactive Engagement ---
    ENABLE_PROACTIVE_MESSAGING: bool = False
    PROACTIVE_CHECK_INTERVAL_MINUTES: int = 60
    PROACTIVE_MIN_TRUST_SCORE: int = 20
    PROACTIVE_SILENCE_THRESHOLD_HOURS: int = 24

    # --- Channel Lurking ---
    ENABLE_CHANNEL_LURKING: bool = False  # Feature flag
    LURK_CONFIDENCE_THRESHOLD: float = 0.7  # Min score to respond (0.0-1.0)
    LURK_CHANNEL_COOLDOWN_MINUTES: int = 30  # Per-channel cooldown
    LURK_USER_COOLDOWN_MINUTES: int = 60  # Per-user cooldown
    LURK_DAILY_MAX_RESPONSES: int = 20  # Global daily limit per bot

    # --- Autonomous Activity (Phase E12) ---
    ENABLE_AUTONOMOUS_ACTIVITY: bool = False  # Master switch for all autonomous activity
    ENABLE_AUTONOMOUS_REACTIONS: bool = False  # React to messages with emojis
    REACTION_CHANNEL_HOURLY_MAX: int = 10  # Max reactions per channel per hour
    REACTION_SAME_USER_COOLDOWN_SECONDS: int = 300  # Min seconds between reactions to same user
    REACTION_DAILY_MAX: int = 100  # Global daily limit for reactions

    # --- Manipulation Timeout ---
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
    DIARY_GENERATION_LOCAL_HOUR: int = 20  # Local hour (in character's timezone) when diary is generated (8 PM)
    DIARY_GENERATION_LOCAL_MINUTE: int = 30  # Local minute when diary is generated
    
    # --- Session Summarization ---
    SUMMARY_MESSAGE_THRESHOLD: int = 20  # Messages per session before auto-summarization

    # --- Dream Sequences (Phase E3) ---
    ENABLE_DREAM_SEQUENCES: bool = True  # Generate dreams when user returns after long absence
    DREAM_INACTIVITY_HOURS: int = 24  # Hours of inactivity before triggering a dream
    DREAM_COOLDOWN_DAYS: int = 7  # Minimum days between dreams for the same user
    DREAM_ALWAYS_GENERATE: bool = True  # Generate nightly dream even without user interactions
    DREAM_GENERATION_LOCAL_HOUR: int = 6  # Local hour (in character's timezone) when dreams are generated (6 AM)
    DREAM_GENERATION_LOCAL_MINUTE: int = 30  # Local minute when dreams are generated
    
    # --- Agentic Narrative Generation (Phase E10) ---
    # When enabled, diary/dream generation uses the DreamWeaver agent which:
    # 1. Plans the narrative arc (story structure, emotional journey)
    # 2. Uses tools to gather correlated data from multiple sources
    # 3. Takes extended steps since it's batch mode (no user waiting)
    # This produces richer, more coherent narratives but uses more LLM tokens.
    ENABLE_AGENTIC_NARRATIVES: bool = False  # Use reflective agent for diary/dream generation

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

    # --- Cross-Bot Chat (Phase E6) ---
    ENABLE_CROSS_BOT_CHAT: bool = True  # Allow bots to respond to each other
    CROSS_BOT_MAX_CHAIN: int = 3  # Max replies in a bot-to-bot chain before stopping
    CROSS_BOT_COOLDOWN_MINUTES: int = 10  # Cooldown per channel between cross-bot interactions
    CROSS_BOT_RESPONSE_CHANCE: float = 0.7  # Probability of responding to another bot's mention (0.0-1.0)

    # --- Scheduled Reminders (Phase E5) ---
    ENABLE_REMINDERS: bool = True  # Enable reminder system

    # --- Stigmergic Shared Artifacts (Phase E13) ---
    ENABLE_STIGMERGIC_DISCOVERY: bool = True  # Allow bots to discover each other's artifacts
    STIGMERGIC_CONFIDENCE_THRESHOLD: float = 0.7  # Min confidence for cross-bot artifacts
    STIGMERGIC_DISCOVERY_LIMIT: int = 3  # Max artifacts from other bots per query

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
