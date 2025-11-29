from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger
import datetime
import dateparser

from src_v2.intelligence.reminder_manager import reminder_manager
from src_v2.evolution.trust import trust_manager

class SetReminderInput(BaseModel):
    content: str = Field(description="What to remind the user about (e.g., 'take out the pizza')")
    time_string: str = Field(description="When to remind them (e.g., 'in 20 minutes', 'tomorrow at 5pm', 'next Tuesday')")

class SetReminderTool(BaseTool):
    name: str = "set_reminder"
    description: str = "Schedules a reminder for the user. Use this when the user asks to be reminded of something at a specific time."
    args_schema: Type[BaseModel] = SetReminderInput
    
    # Injected dependencies
    user_id: str
    channel_id: str
    character_name: str

    def _run(self, content: str, time_string: str) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, content: str, time_string: str) -> str:
        try:
            # 1. Get User Timezone
            user_timezone = "UTC"
            try:
                relationship = await trust_manager.get_relationship_level(self.user_id, self.character_name)
                if relationship and "preferences" in relationship:
                    user_timezone = relationship["preferences"].get("timezone", "UTC")
            except Exception as e:
                logger.warning(f"Failed to fetch user timezone for reminder: {e}")

            # 2. Parse Time
            # dateparser settings to respect user timezone
            parse_settings = {
                'TIMEZONE': user_timezone,
                'RETURN_AS_TIMEZONE_AWARE': True,
                'PREFER_DATES_FROM': 'future'
            }
            
            dt = dateparser.parse(time_string, settings=parse_settings)
            
            if not dt:
                return f"I couldn't understand the time '{time_string}'. Please try saying it differently (e.g., 'in 10 minutes' or 'at 5pm')."
            
            # Ensure UTC for storage
            dt_utc = dt.astimezone(datetime.timezone.utc)
            
            # Check if time is in the past
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if dt_utc < now_utc:
                return f"That time ({time_string}) seems to be in the past. Please specify a future time."

            # 3. Create Reminder
            await reminder_manager.create_reminder(
                user_id=self.user_id,
                channel_id=self.channel_id,
                character_name=self.character_name,
                content=content,
                deliver_at=dt_utc
            )
            
            # Format display time for user
            display_time = dt.strftime("%I:%M %p on %A, %B %d")
            if user_timezone != "UTC":
                display_time += f" ({user_timezone})"
            
            return f"✅ Reminder set! I'll remind you to '{content}' at {display_time}."
            
        except Exception as e:
            logger.error(f"Failed to set reminder: {e}")
            return "I encountered an error while trying to set that reminder. Please try again."
