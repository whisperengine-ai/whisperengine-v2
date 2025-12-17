import discord
import asyncio
import time
from typing import List, Optional
from loguru import logger
from src_v2.config.settings import settings

class ReflectiveStatusManager:
    """
    Manages the reflective agent status updates (thinking, tools, results).
    Handles debouncing and message editing to avoid Discord rate limits.
    """
    def __init__(self, message: discord.Message, use_reply: bool):
        self.trigger_message = message
        self.use_reply = use_reply
        self.status_message: Optional[discord.Message] = None
        self.status_lines: List[str] = []
        self.status_lock = asyncio.Lock()
        self.last_status_update = 0.0
        self.status_debounce_interval = 1.0
        self.pending_update = False

    async def update(self, text: str):
        """
        Callback for reflective agent status updates.
        """
        if settings.REFLECTIVE_STATUS_VERBOSITY == "none":
            return

        async with self.status_lock:
            clean_text = text.strip()
            if not clean_text:
                return

            # Parse prefix to determine update type
            if clean_text.startswith("HEADER:"):
                header = clean_text.replace("HEADER:", "").strip()
                if self.status_lines:
                    self.status_lines[0] = f"**{header}**"
                else:
                    self.status_lines = [f"**{header}**"]
                self.pending_update = True
            elif clean_text.startswith("TOOLS:"):
                content = clean_text.replace("TOOLS:", "").strip()
                self.status_lines.append(content)
                self.pending_update = True
            elif clean_text.startswith("RESULT:"):
                content = clean_text.replace("RESULT:", "").strip()
                self.status_lines.append(content)
                self.pending_update = True
            elif clean_text.startswith("💭") or clean_text:
                if settings.REFLECTIVE_STATUS_VERBOSITY == "detailed":
                    formatted = "\n".join([f"> {line}" for line in clean_text.split("\n")])
                    self.status_lines.append(formatted)
                    self.pending_update = True

            if not self.pending_update or not self.status_lines:
                return

            # Add header if not present
            if not self.status_lines[0].startswith("**"):
                self.status_lines.insert(0, "**🧠 Thinking...**")

            full_content = "\n".join(self.status_lines)

            # Truncate if too long
            if len(full_content) > 1900:
                full_content = full_content[:1900] + "\n... *(truncated)*"

            # Debounce logic
            now = time.time()
            is_first_message = self.status_message is None
            time_since_last = now - self.last_status_update

            if is_first_message or time_since_last >= self.status_debounce_interval:
                try:
                    if self.status_message:
                        await self.status_message.edit(content=full_content)
                    else:
                        if self.use_reply:
                            self.status_message = await self.trigger_message.reply(full_content, mention_author=False)
                        else:
                            self.status_message = await self.trigger_message.channel.send(full_content)
                    self.last_status_update = now
                    self.pending_update = False
                except discord.HTTPException as e:
                    logger.warning(f"Failed to update reflective status: {e}")

    def get_current_content(self) -> str:
        return "\n".join(self.status_lines)
