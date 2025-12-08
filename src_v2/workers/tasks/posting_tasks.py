from typing import Dict, Any
from loguru import logger
from src_v2.agents.posting_agent import PostingAgent


async def run_posting_agent(ctx: Dict[str, Any], bot_name: str) -> Dict[str, Any]:
    """
    Worker task to run the posting agent.
    
    Args:
        ctx: arq context
        bot_name: Character/bot name
        
    Returns:
        Dict with success status and details
    """
    logger.info(f"Running posting agent for {bot_name}")
    
    try:
        agent = PostingAgent()
        success = await agent.generate_and_schedule_post(bot_name)
        
        return {
            "success": success,
            "bot_name": bot_name,
            "posted": success
        }
    except Exception as e:
        logger.error(f"Posting agent failed for {bot_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "bot_name": bot_name
        }
