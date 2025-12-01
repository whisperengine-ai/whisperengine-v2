"""
Unified Artifact System

Handles storage, retrieval, and delivery of generated artifacts
(images, audio, documents) from tools to Discord.
"""

from src_v2.artifacts.registry import (
    artifact_registry,
    ArtifactType,
    Artifact,
    ArtifactMetadata
)
from src_v2.artifacts.discord_utils import extract_pending_artifacts

__all__ = [
    'artifact_registry',
    'ArtifactType',
    'Artifact', 
    'ArtifactMetadata',
    'extract_pending_artifacts'
]
