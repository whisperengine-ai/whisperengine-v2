"""
Artifact Registry - Unified storage for generated artifacts.

Stores images, audio files, and documents in Redis with file backing,
allowing tools to generate artifacts and Discord handlers to retrieve them.
"""

import json
import aiofiles
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from loguru import logger

from src_v2.config.settings import settings


class ArtifactType(str, Enum):
    """Types of artifacts that can be stored."""
    IMAGE = "image"
    AUDIO = "audio"
    DOCUMENT = "document"


@dataclass
class ArtifactMetadata:
    """Metadata for an artifact."""
    type: ArtifactType
    filename: str
    mime_type: str
    source_tool: str  # e.g., "generate_image", "voice_response"
    prompt: Optional[str] = None  # For images/audio generation
    extra: Optional[Dict[str, Any]] = None  # Tool-specific metadata


@dataclass
class Artifact:
    """A generated artifact ready for delivery."""
    metadata: ArtifactMetadata
    data: bytes  # The raw file data
    
    @property
    def filename(self) -> str:
        return self.metadata.filename
    
    @property
    def type(self) -> ArtifactType:
        return self.metadata.type


class ArtifactRegistry:
    """
    Redis-backed artifact storage with file caching.
    
    Artifacts are stored as:
    - File bytes on disk (temp_downloads/{user_id}/{filename})
    - Metadata in Redis (artifacts:{user_id} as a list)
    
    TTL: 5 minutes (enough time for Discord to fetch after response)
    """
    
    def __init__(self, storage_dir: str = "temp_downloads", ttl: int = 300):
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(exist_ok=True)
        self._ttl = ttl
        self._redis = None
    
    async def _get_redis(self):
        """Lazy Redis connection."""
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(settings.REDIS_URL)
        return self._redis
    
    def _user_dir(self, user_id: str) -> Path:
        """Get user-specific storage directory."""
        user_dir = self._storage_dir / user_id
        user_dir.mkdir(exist_ok=True)
        return user_dir
    
    async def add(
        self,
        user_id: str,
        artifact_type: ArtifactType,
        data: bytes,
        filename: str,
        mime_type: str,
        source_tool: str,
        prompt: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Add an artifact to the registry.
        
        Args:
            user_id: The user this artifact is for
            artifact_type: Type of artifact (image, audio, document)
            data: Raw file bytes
            filename: Display filename
            mime_type: MIME type (e.g., "image/png", "audio/mp3")
            source_tool: Name of the tool that generated this
            prompt: Optional generation prompt
            extra: Optional tool-specific metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # 1. Save file to disk
            filepath = self._user_dir(user_id) / filename
            async with aiofiles.open(filepath, "wb") as f:
                await f.write(data)
            
            # 2. Build metadata
            metadata = {
                "type": artifact_type.value,
                "filename": filename,
                "mime_type": mime_type,
                "source_tool": source_tool,
                "prompt": prompt,
                "extra": extra or {},
                "path": str(filepath)  # For retrieval
            }
            
            # 3. Store in Redis
            key = f"artifacts:{user_id}"
            r = await self._get_redis()
            await r.rpush(key, json.dumps(metadata))
            await r.expire(key, self._ttl)
            
            logger.debug(f"Artifact registered: {artifact_type.value}/{filename} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add artifact to registry: {e}")
            return False
    
    async def add_image(
        self,
        user_id: str,
        data: bytes,
        filename: str,
        prompt: Optional[str] = None,
        seed: Optional[int] = None,
        url: Optional[str] = None
    ) -> bool:
        """Convenience method for adding images."""
        extra = {}
        if seed is not None:
            extra["seed"] = seed
        if url:
            extra["url"] = url
            
        return await self.add(
            user_id=user_id,
            artifact_type=ArtifactType.IMAGE,
            data=data,
            filename=filename,
            mime_type="image/png",
            source_tool="generate_image",
            prompt=prompt,
            extra=extra if extra else None
        )
    
    async def add_audio(
        self,
        user_id: str,
        data: bytes,
        filename: str,
        text: Optional[str] = None,
        voice_id: Optional[str] = None
    ) -> bool:
        """Convenience method for adding audio."""
        extra = {}
        if voice_id:
            extra["voice_id"] = voice_id
            
        return await self.add(
            user_id=user_id,
            artifact_type=ArtifactType.AUDIO,
            data=data,
            filename=filename,
            mime_type="audio/mpeg",
            source_tool="voice_response",
            prompt=text,
            extra=extra if extra else None
        )
    
    async def pop_all(self, user_id: str) -> List[Artifact]:
        """
        Retrieve all pending artifacts for a user, load data, and cleanup.
        
        Returns:
            List of Artifact objects with loaded data
        """
        key = f"artifacts:{user_id}"
        results = []
        
        try:
            r = await self._get_redis()
            
            # Get all items
            while True:
                raw = await r.lpop(key)
                if not raw:
                    break
                
                try:
                    meta = json.loads(raw)
                    path = Path(meta["path"])
                    
                    if path.exists():
                        # Load bytes
                        async with aiofiles.open(path, "rb") as f:
                            data = await f.read()
                        
                        # Build artifact
                        artifact_meta = ArtifactMetadata(
                            type=ArtifactType(meta["type"]),
                            filename=meta["filename"],
                            mime_type=meta["mime_type"],
                            source_tool=meta["source_tool"],
                            prompt=meta.get("prompt"),
                            extra=meta.get("extra")
                        )
                        results.append(Artifact(metadata=artifact_meta, data=data))
                        
                        # Cleanup file
                        path.unlink()
                        logger.debug(f"Retrieved and cleaned up artifact: {path}")
                    else:
                        logger.warning(f"Artifact file not found: {path}")
                        
                except Exception as e:
                    logger.error(f"Error processing artifact item: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to retrieve artifacts from Redis: {e}")
            return []
    
    async def pop_by_type(self, user_id: str, artifact_type: ArtifactType) -> List[Artifact]:
        """
        Retrieve artifacts of a specific type for a user.
        Other types remain in the queue.
        """
        all_artifacts = await self.pop_all(user_id)
        
        matching = []
        remaining = []
        
        for artifact in all_artifacts:
            if artifact.type == artifact_type:
                matching.append(artifact)
            else:
                remaining.append(artifact)
        
        # Re-add non-matching artifacts
        for artifact in remaining:
            await self.add(
                user_id=user_id,
                artifact_type=artifact.type,
                data=artifact.data,
                filename=artifact.filename,
                mime_type=artifact.metadata.mime_type,
                source_tool=artifact.metadata.source_tool,
                prompt=artifact.metadata.prompt,
                extra=artifact.metadata.extra
            )
        
        return matching
    
    async def count(self, user_id: str) -> int:
        """Get count of pending artifacts for a user."""
        try:
            r = await self._get_redis()
            return await r.llen(f"artifacts:{user_id}")
        except Exception as e:
            logger.error(f"Failed to count artifacts: {e}")
            return 0
    
    async def clear(self, user_id: str) -> int:
        """Clear all pending artifacts for a user. Returns count cleared."""
        try:
            # Pop all to cleanup files
            artifacts = await self.pop_all(user_id)
            return len(artifacts)
        except Exception as e:
            logger.error(f"Failed to clear artifacts: {e}")
            return 0


# Global registry instance
artifact_registry = ArtifactRegistry()
