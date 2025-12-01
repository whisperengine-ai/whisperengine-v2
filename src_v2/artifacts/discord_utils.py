"""
Discord utilities for artifact delivery.

Extracts pending artifacts from the registry and converts them to Discord files.
"""

import io
from typing import List, Tuple
import discord
from loguru import logger

from src_v2.artifacts.registry import artifact_registry, ArtifactType, Artifact


async def extract_pending_artifacts(user_id: str) -> List[discord.File]:
    """
    Retrieve all pending artifacts for a user and convert to Discord Files.
    
    Args:
        user_id: The user to retrieve artifacts for
        
    Returns:
        List of discord.File objects ready for sending
    """
    try:
        artifacts = await artifact_registry.pop_all(user_id)
        
        files = []
        for artifact in artifacts:
            file = discord.File(
                fp=io.BytesIO(artifact.data),
                filename=artifact.filename
            )
            files.append(file)
            logger.debug(f"Converted artifact to Discord file: {artifact.filename}")
        
        return files
        
    except Exception as e:
        logger.error(f"Failed to extract artifacts for user {user_id}: {e}")
        return []


async def extract_images(user_id: str) -> List[discord.File]:
    """Extract only image artifacts."""
    try:
        artifacts = await artifact_registry.pop_by_type(user_id, ArtifactType.IMAGE)
        return [
            discord.File(fp=io.BytesIO(a.data), filename=a.filename)
            for a in artifacts
        ]
    except Exception as e:
        logger.error(f"Failed to extract images for user {user_id}: {e}")
        return []


async def extract_audio(user_id: str) -> List[discord.File]:
    """Extract only audio artifacts."""
    try:
        artifacts = await artifact_registry.pop_by_type(user_id, ArtifactType.AUDIO)
        return [
            discord.File(fp=io.BytesIO(a.data), filename=a.filename)
            for a in artifacts
        ]
    except Exception as e:
        logger.error(f"Failed to extract audio for user {user_id}: {e}")
        return []


async def has_pending_artifacts(user_id: str) -> bool:
    """Check if user has any pending artifacts."""
    count = await artifact_registry.count(user_id)
    return count > 0
