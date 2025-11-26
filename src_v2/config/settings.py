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
    
    # --- Router LLM Configuration (Optional - for faster/cheaper routing) ---
    ROUTER_LLM_PROVIDER: Optional[Literal["openai", "openrouter", "ollama", "lmstudio"]] = None
    ROUTER_LLM_API_KEY: Optional[SecretStr] = None
    ROUTER_LLM_BASE_URL: Optional[str] = None
    ROUTER_LLM_MODEL_NAME: Optional[str] = None
    
    # --- Reflective LLM Configuration (Optional - for deep thinking ReAct mode) ---
    REFLECTIVE_LLM_PROVIDER: Optional[Literal["openai", "openrouter", "ollama", "lmstudio"]] = None
    REFLECTIVE_LLM_API_KEY: Optional[SecretStr] = None
    REFLECTIVE_LLM_BASE_URL: Optional[str] = None
    REFLECTIVE_LLM_MODEL_NAME: Optional[str] = None

    # --- Discord ---
    DISCORD_TOKEN: SecretStr = Field(validation_alias=AliasChoices("DISCORD_TOKEN", "DISCORD_BOT_TOKEN"))

    # --- Databases ---
    # PostgreSQL
    POSTGRES_URL: str = Field(default="postgresql://whisper:password@localhost:5432/whisperengine_v2")
    
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

    # --- Knowledge Graph ---
    ENABLE_RUNTIME_FACT_EXTRACTION: bool = True

    # --- Preference Extraction ---
    ENABLE_PREFERENCE_EXTRACTION: bool = True

    # --- Proactive Engagement ---
    ENABLE_PROACTIVE_MESSAGING: bool = False

    # --- Debugging ---
    ENABLE_PROMPT_LOGGING: bool = False

    # --- Privacy & Security ---
    ENABLE_DM_BLOCK: bool = True
    DM_ALLOWED_USER_IDS: str = Field(default="", description="List of Discord User IDs allowed to DM the bot (comma-separated)")

    @property
    def dm_allowed_user_ids_list(self) -> list[str]:
        v = self.DM_ALLOWED_USER_IDS
        if not v.strip():
            return []
        # Support JSON format for backward compatibility
        if v.strip().startswith("["):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                pass
        # Support comma-separated list
        return [id.strip() for id in v.split(",") if id.strip()]

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
