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
    DISCORD_TOKEN: SecretStr = Field(validation_alias=AliasChoices("DISCORD_TOKEN", "DISCORD_BOT_TOKEN"))
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
    
    # --- API ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # --- Reflective Mode Configuration ---
    ENABLE_REFLECTIVE_MODE: bool = False
    ENABLE_CHARACTER_AGENCY: bool = True  # Phase A7: Tier 2 Tool Usage
    REFLECTIVE_LLM_PROVIDER: str = "openrouter"
    REFLECTIVE_LLM_MODEL_NAME: str = "anthropic/claude-3.5-sonnet"
    REFLECTIVE_LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    REFLECTIVE_LLM_API_KEY: Optional[SecretStr] = None
    REFLECTIVE_MAX_STEPS: int = 10
    REFLECTIVE_MEMORY_RESULT_LIMIT: int = 3  # Max results returned per memory search

    # --- Bot Identity ---
    DISCORD_BOT_NAME: Optional[str] = Field(default=None, description="Name of the bot/character (e.g. elena)")

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

    # --- Manipulation Timeout ---
    ENABLE_MANIPULATION_TIMEOUTS: bool = False  # Track and timeout manipulation attempts (disabled by default)

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
