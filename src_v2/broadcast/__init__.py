"""
Bot Broadcast System (Phase E8)

Enables bots to post thoughts, dreams, and observations to a public Discord channel.
Other bots can discover and react to these posts, creating emergent cross-character awareness.
"""

from src_v2.broadcast.manager import BroadcastManager, broadcast_manager

__all__ = ["BroadcastManager", "broadcast_manager"]
