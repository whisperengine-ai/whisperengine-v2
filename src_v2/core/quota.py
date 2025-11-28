from datetime import date
from loguru import logger
from src_v2.core.database import db_manager, retry_db_operation
from src_v2.config.settings import settings

class QuotaManager:
    @retry_db_operation()
    async def check_quota(self, user_id: str, quota_type: str) -> bool:
        """
        Check if user has quota remaining for the given type ('image' or 'audio').
        Returns True if quota is available, False otherwise.
        """
        if not db_manager.postgres_pool:
            logger.warning("Postgres not available, allowing quota check by default")
            return True

        today = date.today()
        limit = settings.DAILY_IMAGE_QUOTA if quota_type == 'image' else settings.DAILY_AUDIO_QUOTA
        
        query = """
            SELECT image_count, audio_count 
            FROM v2_user_daily_usage 
            WHERE user_id = $1 AND date = $2
        """
        
        async with db_manager.postgres_pool.acquire() as conn:
            row = await conn.fetchrow(query, str(user_id), today)
            
            if not row:
                return True # No usage yet today
            
            current_usage = row['image_count'] if quota_type == 'image' else row['audio_count']
            
            if current_usage >= limit:
                logger.info(f"User {user_id} hit {quota_type} quota ({current_usage}/{limit})")
                return False
                
            return True

    @retry_db_operation()
    async def increment_usage(self, user_id: str, quota_type: str) -> None:
        """
        Increment usage for the given type.
        """
        if not db_manager.postgres_pool:
            return

        today = date.today()
        
        # Upsert query
        query = """
            INSERT INTO v2_user_daily_usage (user_id, date, image_count, audio_count)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, date) 
            DO UPDATE SET 
                image_count = v2_user_daily_usage.image_count + $3,
                audio_count = v2_user_daily_usage.audio_count + $4,
                updated_at = NOW()
        """
        
        img_inc = 1 if quota_type == 'image' else 0
        audio_inc = 1 if quota_type == 'audio' else 0
        
        async with db_manager.postgres_pool.acquire() as conn:
            await conn.execute(query, str(user_id), today, img_inc, audio_inc)
            logger.info(f"Incremented {quota_type} usage for user {user_id}")

quota_manager = QuotaManager()
