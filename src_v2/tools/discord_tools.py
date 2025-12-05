import discord
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger
from datetime import datetime, timezone

from src_v2.utils.validation import smart_truncate

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


def format_message(msg: discord.Message, indent: str = "") -> str:
    """Format a Discord message for display.
    
    Args:
        msg: Discord message object
        indent: Optional prefix for indentation (e.g. "    " for context messages)
    
    Returns:
        Formatted string like "[5m ago] Username (Bot): message content..."
    """
    timestamp = format_relative_time(msg.created_at)
    author = msg.author.display_name
    is_bot = " (Bot)" if msg.author.bot else ""
    content = smart_truncate(msg.content, max_length=300)
    return f"{indent}[{timestamp}] {author}{is_bot}: {content}"

class SearchChannelMessagesInput(BaseModel):
    query: str = Field(description="Keyword or topic to search for in messages")
    limit: int = Field(default=10, description="Max number of matching messages to return (default 10)")

class SearchChannelMessagesTool(BaseTool):
    name: str = "search_channel_messages"
    description: str = """Search the CURRENT CHANNEL's recent Discord messages by keyword. Only scans last 200 messages in THIS channel.

USE THIS FOR: "what did I say earlier?" (in this channel), "what happened in chat?", recent channel-specific context.
DO NOT USE FOR: Memories from DMs, past conversations from other channels, or long-term memory recall.

For memories across all contexts (DMs, other channels), use search_specific_memories instead."""
    args_schema: Type[BaseModel] = SearchChannelMessagesInput
    
    # Injected at runtime
    channel: Optional[discord.abc.Messageable] = Field(default=None, exclude=True)

    def _run(self, query: str, limit: int = 10) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query: str, limit: int = 10) -> str:
        if not self.channel:
            return "Error: No channel context available for search."
            
        try:
            # Scan depth - how far back to look
            scan_depth = 200
            limit = min(limit, 50) # Max results to return
            
            messages = []
            
            # We need to iterate over history. 
            # Note: history() is an async iterator in discord.py
            async for msg in self.channel.history(limit=scan_depth): # type: ignore
                if not msg.content:
                    continue
                    
                if query.lower() in msg.content.lower():
                    messages.append(format_message(msg))
                    if len(messages) >= limit:
                        break
            
            if not messages:
                return f"No messages found matching '{query}' in the last {scan_depth} messages."
            
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
            search_limit = 200 
            found_messages = []
            target_user_lower = user_name.lower()
            
            async for msg in self.channel.history(limit=search_limit): # type: ignore
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
                    
                    found_messages.append(format_message(msg))
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


class GetMessageContextInput(BaseModel):
    message_id: str = Field(description="Discord message ID to get context around")
    before: int = Field(default=5, description="Number of messages before (default 5)")
    after: int = Field(default=5, description="Number of messages after (default 5)")

class GetMessageContextTool(BaseTool):
    name: str = "get_message_context"
    description: str = "Get messages surrounding a specific message ID. Use when user replies to an old message and you need context, or to understand what led to a specific message."
    args_schema: Type[BaseModel] = GetMessageContextInput
    
    channel: Optional[discord.abc.Messageable] = Field(default=None, exclude=True)

    def _run(self, message_id: str, before: int = 5, after: int = 5) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, message_id: str, before: int = 5, after: int = 5) -> str:
        if not self.channel:
            return "Error: No channel context available."
            
        try:
            # Validate and convert message_id to int
            try:
                message_id_int = int(message_id)
            except (ValueError, TypeError):
                return f"Error: Invalid message ID format '{message_id}'. Expected a numeric ID."
            
            # Fetch the target message
            target_msg = await self.channel.fetch_message(message_id_int) # type: ignore
            
            # Get messages before
            before_msgs = []
            async for msg in self.channel.history(limit=before, before=target_msg): # type: ignore
                if msg.content:
                    before_msgs.append(format_message(msg, indent="    "))
            before_msgs.reverse()
            
            # Get messages after
            after_msgs = []
            async for msg in self.channel.history(limit=after, after=target_msg): # type: ignore
                if msg.content:
                    after_msgs.append(format_message(msg, indent="    "))
            
            # Format target message (highlighted with >>>)
            target_formatted = format_message(target_msg, indent=">>> ")
            
            # Combine all
            all_msgs = before_msgs + [target_formatted] + after_msgs
            return "\n".join(all_msgs) if all_msgs else "No context found around this message."
            
        except discord.NotFound:
            return f"Message with ID {message_id} not found."
        except Exception as e:
            logger.error(f"Error getting message context: {e}")
            return f"Error getting message context: {str(e)}"


class GetRecentMessagesInput(BaseModel):
    limit: int = Field(default=15, description="Number of recent messages to fetch (default 15, max 50)")

class GetRecentMessagesTool(BaseTool):
    name: str = "get_recent_messages"
    description: str = "Get the most recent messages in the channel without filtering. Use for 'catch me up', 'what's happening?', or general channel context."
    args_schema: Type[BaseModel] = GetRecentMessagesInput
    
    channel: Optional[discord.abc.Messageable] = Field(default=None, exclude=True)

    def _run(self, limit: int = 15) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, limit: int = 15) -> str:
        if not self.channel:
            return "Error: No channel context available."
            
        try:
            limit = min(limit, 50)  # Safety cap
            messages = []
            
            async for msg in self.channel.history(limit=limit): # type: ignore
                if not msg.content:
                    continue
                messages.append(format_message(msg))
            
            if not messages:
                return "No recent messages in this channel."
            
            messages.reverse()
            return "\n".join(messages)
            
        except Exception as e:
            logger.error(f"Error fetching recent messages: {e}")
            return f"Error fetching recent messages: {str(e)}"
