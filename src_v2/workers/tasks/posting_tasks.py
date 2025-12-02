from typing import Dict, Any
from loguru import logger
from src_v2.agents.posting_agent import run_posting_agent as agent_run

async def run_posting_agent(ctx: Dict[str, Any], bot_name: str) -> None:
    """
    Worker task to run the posting agent.
    """
    logger.info(f"Running posting agent for {bot_name}")
    await agent_run(ctx, bot_name)
