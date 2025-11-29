"""
User Timezone Inference and Management (Phase S4)

Infers user timezone from Discord activity patterns and manages quiet hours
for proactive messaging. Prevents bots from messaging users at 3 AM.
"""

from typing import Optional, Tuple, List
from datetime import datetime, timezone as tz
from collections import Counter
from dataclasses import dataclass
from loguru import logger

from src_v2.core.database import db_manager

# Mapping of peak UTC hours to likely timezones
# Based on assumption that users are most active during afternoon/evening (14:00-22:00 local)
TIMEZONE_ESTIMATES = {
    # Peak at 14-18 UTC → Likely in UTC+0 to UTC+2 (Europe/UK)
    (14, 15, 16, 17, 18): "Europe/London",
    # Peak at 18-22 UTC → Likely in UTC-4 to UTC-5 (US East)
    (18, 19, 20, 21, 22): "America/New_York",
    # Peak at 21-01 UTC → Likely in UTC-7 to UTC-8 (US West)
    (21, 22, 23, 0, 1): "America/Los_Angeles",
    # Peak at 06-10 UTC → Likely in UTC+8 to UTC+9 (Asia/Pacific)
    (6, 7, 8, 9, 10): "Asia/Tokyo",
    # Peak at 10-14 UTC → Likely in UTC+5 to UTC+6 (India/Central Asia)
    (10, 11, 12, 13, 14): "Asia/Kolkata",
}


@dataclass
class UserTimeSettings:
    """User's timezone and quiet hours settings."""
    timezone: Optional[str] = None
    timezone_confidence: float = 0.0
    quiet_hours_start: int = 22  # 10 PM local
    quiet_hours_end: int = 8     # 8 AM local


class TimezoneManager:
    """
    Manages user timezone inference and quiet hours checking.
    """
    
    async def get_user_time_settings(self, user_id: str, character_name: str) -> UserTimeSettings:
        """Get timezone settings for a user."""
        if not db_manager.postgres_pool:
            return UserTimeSettings()
        
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT timezone, timezone_confidence, quiet_hours_start, quiet_hours_end
                    FROM v2_user_relationships
                    WHERE user_id = $1 AND character_name = $2
                """, user_id, character_name)
                
                if row:
                    return UserTimeSettings(
                        timezone=row['timezone'],
                        timezone_confidence=row['timezone_confidence'] or 0.0,
                        quiet_hours_start=row['quiet_hours_start'] or 22,
                        quiet_hours_end=row['quiet_hours_end'] or 8
                    )
        except Exception as e:
            logger.warning(f"Failed to get user time settings: {e}")
        
        return UserTimeSettings()
    
    async def save_inferred_timezone(
        self, 
        user_id: str, 
        character_name: str, 
        timezone: str, 
        confidence: float
    ) -> None:
        """Save an inferred timezone for a user."""
        if not db_manager.postgres_pool:
            return
        
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE v2_user_relationships
                    SET timezone = $1, timezone_confidence = $2
                    WHERE user_id = $3 AND character_name = $4
                    AND (timezone IS NULL OR timezone_confidence < $2)
                """, timezone, confidence, user_id, character_name)
                
                logger.debug(f"Saved inferred timezone {timezone} (confidence: {confidence:.2f}) for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to save inferred timezone: {e}")
    
    async def infer_timezone_from_activity(
        self, 
        user_id: str, 
        character_name: str
    ) -> Tuple[Optional[str], float]:
        """
        Infer user timezone from their message timestamps.
        
        Returns:
            Tuple of (timezone_string, confidence_score)
            confidence_score is 0.0-1.0 based on how consistent the pattern is
        """
        if not db_manager.postgres_pool:
            return None, 0.0
        
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Get last 200 message timestamps for this user
                rows = await conn.fetch("""
                    SELECT created_at 
                    FROM v2_chat_history
                    WHERE user_id = $1 AND character_name = $2 AND role = 'user'
                    ORDER BY created_at DESC
                    LIMIT 200
                """, user_id, character_name)
                
                if len(rows) < 20:
                    # Not enough data to infer
                    return None, 0.0
                
                # Count messages by UTC hour
                hour_counts = Counter()
                for row in rows:
                    ts = row['created_at']
                    if ts:
                        hour_counts[ts.hour] += 1
                
                # Find the 4 most active hours
                peak_hours = [h for h, _ in hour_counts.most_common(4)]
                
                if not peak_hours:
                    return None, 0.0
                
                # Match peak hours to timezone estimates
                best_match = None
                best_overlap = 0
                
                for tz_hours, tz_name in TIMEZONE_ESTIMATES.items():
                    overlap = len(set(peak_hours) & set(tz_hours))
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_match = tz_name
                
                if best_match and best_overlap >= 2:
                    # Confidence based on overlap and consistency
                    confidence = min(0.9, best_overlap / 4 * 0.8 + len(rows) / 200 * 0.2)
                    return best_match, confidence
                
                return None, 0.0
                
        except Exception as e:
            logger.warning(f"Failed to infer timezone: {e}")
            return None, 0.0
    
    def is_quiet_hours(self, settings: UserTimeSettings) -> bool:
        """
        Check if it's currently quiet hours for the user.
        
        Returns True if we should NOT message the user.
        """
        if not settings.timezone:
            # No timezone known - allow messaging (better to message than not)
            return False
        
        try:
            import pytz
            user_tz = pytz.timezone(settings.timezone)
            user_time = datetime.now(user_tz)
            user_hour = user_time.hour
            
            start = settings.quiet_hours_start
            end = settings.quiet_hours_end
            
            # Handle overnight ranges like 22-8 (10 PM to 8 AM)
            if start <= end:
                # Simple range: e.g., 1-6 (1 AM to 6 AM)
                in_quiet = start <= user_hour < end
            else:
                # Overnight range: e.g., 22-8 (10 PM to 8 AM)
                in_quiet = user_hour >= start or user_hour < end
            
            return in_quiet
            
        except Exception as e:
            logger.warning(f"Failed to check quiet hours: {e}")
            return False


# Global instance
timezone_manager = TimezoneManager()
