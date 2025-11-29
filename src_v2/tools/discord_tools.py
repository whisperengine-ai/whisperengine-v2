import discord
from typing import Type, Optional, List
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger
from datetime import datetime, timezone

def format_relative_time(dt: datetime) -> str:
    """Format datetime as relative time string (e.g. '5m ago')."""
    if not dt:
        return "unknown time"
        
    # Ensure dt is timezone-aware (Discord API returns aware datetimes)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
        
    now = datetime.now(timezone.utc)
    diff = now - dt
    minutes = int(diff.total_seconds() / 60)
    
    if minutes < 1:
        return "just now"
    elif minutes < 60:
        return f"{minutes}m ago"
    elif minutes < 1440:
        hours = int(minutes / 60)
        return f"{hours}h ago"
    else:
        days = int(minutes / 1440)
        return f"{days}d ago"

class SearchChannelMessagesInput(BaseModel):
    query: str = Field(description="Keyword or topic to search for in messages")
    limit: int = Field(default=30, description="Max messages to search (default 30, max 100)")

class SearchChannelMessagesTool(BaseTool):
    name: str = "search_channel_messages"
    description: str = "Search recent channel messages by keyword/topic. Use when user asks 'what did I say about X?', 'what happened earlier?', or references recent conversation."
    args_schema: Type[BaseModel] = SearchChannelMessagesInput
    
    # Injected at runtime
    channel: Optional[discord.abc.Messageable] = Field(default=None, exclude=True)

    def _run(self, query: str, limit: int = 30) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query: str, limit: int = 30) -> str:
        if not self.channel:
            return "Error: No channel context available for search."
            
        try:
            limit = min(limit, 100) # Safety cap
            messages = []
            
            # We need to iterate over history. 
            # Note: history() is an async iterator in discord.py
            async for msg in self.channel.history(limit=limit):
                if not msg.content:
                    continue
                    
                if query.lower() in msg.content.lower():
                    timestamp = format_relative_time(msg.created_at)
                    author = msg.author.display_name
                    is_bot = " (Bot)" if msg.author.bot else ""
                    # Truncate long messages
                    content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
                    messages.append(f"[{timestamp}] {author}{is_bot}: {content}")
            
            if not messages:
                return f"No messages found matching '{query}' in the last {limit} messages."
            
            # Reverse to chronological order (history returns newest first)
            messages.reverse()
            return "\n".join(messages)
            
        except Exception as e:
            logger.error(f"Error searching channel messages: {e}")
            return f"Error searching messages: {str(e)}"

class SearchUserMessagesInput(BaseModel):
    user_name: str = Field(description="Display name or username to search for")
    query: Optional[str] = Field(default=None, description="Optional keyword to filter their messages")
    limit: int = Field(default=20, description="Max messages to return (default 20)")

class SearchUserMessagesTool(BaseTool):
    name: str = "search_user_messages"
    description: str = "Find recent messages from a specific user. Use when asked 'what did Mark say?' or 'find Sarah's last message'."
    args_schema: Type[BaseModel] = SearchUserMessagesInput
    
    # Injected at runtime
    channel: Optional[discord.abc.Messageable] = Field(default=None, exclude=True)

    def _run(self, user_name: str, query: Optional[str] = None, limit: int = 20) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, user_name: str, query: Optional[str] = None, limit: int = 20) -> str:
        if not self.channel:
            return "Error: No channel context available."
            
        try:
            # We need to search more history to find specific user messages
            search_limit = 100 
            found_messages = []
            target_user_lower = user_name.lower()
            
            async for msg in self.channel.history(limit=search_limit):
                if not msg.content:
                    continue
                
                # Check author match (display name or name)
                author_match = (
                    target_user_lower in msg.author.display_name.lower() or 
                    target_user_lower in msg.author.name.lower()
                )
                
                if author_match:
                    # Check query match if provided
                    if query and query.lower() not in msg.content.lower():
                        continue
                        
                    timestamp = format_relative_time(msg.created_at)
                    author = msg.author.display_name
                    content = msg.content[:300]
                    found_messages.append(f"[{timestamp}] {author}: {content}")
                    
                    if len(found_messages) >= limit:
                        break
            
            if not found_messages:
                msg = f"No recent messages found from user '{user_name}'"
                if query:
                    msg += f" containing '{query}'"
                return msg
            
            found_messages.reverse()
            return "\n".join(found_messages)

        except Exception as e:
            logger.error(f"Error searching user messages: {e}")
            return f"Error searching user messages: {str(e)}"
