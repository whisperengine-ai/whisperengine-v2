"""
Execute node - Act phase of the stigmergic loop.

Executes planned actions one at a time, delegating to specialized agents.

Uses ConversationService for unified message processing - same pipeline
as Discord message_handler and HTTP API. Bot messages are first-class citizens.
"""

from typing import Dict, Any, TYPE_CHECKING
from loguru import logger

import discord
from discord.ext import commands

from src_v2.agents.daily_life.state import (
    DailyLifeState,
    PlannedAction,
    ActionResult,
)

if TYPE_CHECKING:
    from src_v2.core.character import Character


# ──────────────────────────────────────────────────────────────────────────────
# DISCORD ACTIONS
# ──────────────────────────────────────────────────────────────────────────────

async def execute_reply(
    action: PlannedAction,
    bot: commands.Bot,
    character: "Character",
    state: DailyLifeState,
) -> ActionResult:
    """Reply to a Discord message using ConversationService.
    
    Uses the unified ConversationService for FULL processing:
    - Same pipeline as message_handler.py and API routes
    - Memory storage (both user and AI messages)
    - Session management
    - Background learning
    
    Bot messages are first-class citizens.
    """
    
    if not action.channel_id or not action.target_message_id:
        return ActionResult(action=action, success=False, error="Missing channel_id or target_message_id")
    
    try:
        # Get channel and message
        channel = bot.get_channel(int(action.channel_id))
        if not channel or not isinstance(channel, discord.TextChannel):
            return ActionResult(action=action, success=False, error=f"Channel {action.channel_id} not found")
        
        message = await channel.fetch_message(int(action.target_message_id))
        if not message:
            return ActionResult(action=action, success=False, error=f"Message {action.target_message_id} not found")
        
        # Use ConversationService for unified processing
        from src_v2.core.conversation import conversation_service, ConversationContext
        
        context = ConversationContext(
            user_id=str(message.author.id),
            user_name=message.author.display_name,
            character_name=character.name,
            user_message=message.content,
            channel_id=str(message.channel.id),
            channel_name=channel.name,
            server_id=str(message.guild.id) if message.guild else None,
            message_id=str(message.id),
            is_cross_bot=message.author.bot,
            source_bot_name=message.author.display_name if message.author.bot else None,
            origin="daily_life",
        )
        
        # Define callback to send message and get ID
        async def send_reply(text: str):
            return await message.reply(text)
        
        result = await conversation_service.process_turn(
            context=context,
            character=character,
            send_callback=send_reply,
        )
        
        if not result.success:
            return ActionResult(action=action, success=False, error=result.error or "Response generation failed")
        
        logger.info(f"[DailyLife] Executed: reply to msg_{action.target_message_id} from {context.user_name}")
        
        # Trigger summarization check (uses message_handler if available)
        await conversation_service.trigger_summarization_check(
            session_id=result.session_id or "",
            user_id=context.user_id,
            user_name=context.user_name,
            channel_id=context.channel_id,
            server_id=context.server_id,
            message_handler=getattr(bot, 'message_handler', None),
        )
        
        return ActionResult(
            action=action,
            success=True,
            message_id=result.response_message_id,
        )
        
    except Exception as e:
        logger.error(f"[DailyLife] Reply failed: {e}")
        return ActionResult(action=action, success=False, error=str(e))


async def execute_react(
    action: PlannedAction,
    bot: commands.Bot,
) -> ActionResult:
    """Add emoji reaction to a message."""
    
    if not action.channel_id or not action.target_message_id or not action.emoji:
        return ActionResult(action=action, success=False, error="Missing channel_id, target_message_id, or emoji")
    
    try:
        channel = bot.get_channel(int(action.channel_id))
        if not channel or not isinstance(channel, discord.TextChannel):
            return ActionResult(action=action, success=False, error=f"Channel {action.channel_id} not found")
        
        message = await channel.fetch_message(int(action.target_message_id))
        if not message:
            return ActionResult(action=action, success=False, error=f"Message {action.target_message_id} not found")
        
        await message.add_reaction(action.emoji)
        
        logger.info(f"[DailyLife] Executed: react {action.emoji} to msg_{action.target_message_id}")
        
        return ActionResult(action=action, success=True)
        
    except Exception as e:
        logger.error(f"[DailyLife] React failed: {e}")
        return ActionResult(action=action, success=False, error=str(e))


async def execute_post(
    action: PlannedAction,
    bot: commands.Bot,
    character: "Character",
) -> ActionResult:
    """Post a new message to a channel using PostingAgent."""
    
    if not action.channel_id:
        return ActionResult(action=action, success=False, error="Missing channel_id")
    
    try:
        channel = bot.get_channel(int(action.channel_id))
        if not channel or not isinstance(channel, discord.TextChannel):
            return ActionResult(action=action, success=False, error=f"Channel {action.channel_id} not found")
        
        # Use PostingAgent to generate and post content
        from src_v2.agents.posting_agent import PostingAgent
        
        posting_agent = PostingAgent()
        
        # If target_bot_name is provided, we need to find their ID to mention them
        mention_text = ""
        if action.target_bot_name:
            # Try to find the bot in the guild
            target_member = discord.utils.find(
                lambda m: m.name == action.target_bot_name or m.display_name == action.target_bot_name, 
                channel.guild.members
            )
            if target_member:
                mention_text = target_member.mention
            else:
                # Fallback to just name if not found
                mention_text = f"@{action.target_bot_name}"
        
        # We need to pass this mention context to the posting agent
        # Currently PostingAgent doesn't accept a prompt override, so we might need to extend it
        # For now, we'll use the standard posting agent but log the intent
        
        context_override = None
        if mention_text:
            context_override = f"You want to start a conversation with {mention_text}. Mention them directly in your message."

        success = await posting_agent.generate_and_schedule_post(
            character_name=character.name,
            target_channel_id=action.channel_id,
            context_override=context_override
        )
        
        if not success:
            return ActionResult(action=action, success=False, error="PostingAgent failed to generate/schedule post")
        
        # If we had a mention, we might want to append it or handle it differently
        # But since PostingAgent handles the actual sending, we can't easily inject it here without modifying PostingAgent
        
        logger.info(f"[DailyLife] Executed: post to #{channel.name} (target_bot={action.target_bot_name})")
        
        return ActionResult(
            action=action,
            success=True,
        )
        
    except Exception as e:
        logger.error(f"[DailyLife] Post failed: {e}")
        return ActionResult(action=action, success=False, error=str(e))


async def execute_reach_out(
    action: PlannedAction,
    bot: commands.Bot,
    character: "Character",
) -> ActionResult:
    """Send a DM to a user we're concerned about.
    
    Uses ConversationService for unified processing - the reach-out
    is stored in memory so the bot remembers initiating contact.
    """
    
    if not action.target_user_id:
        return ActionResult(action=action, success=False, error="Missing target_user_id")
    
    try:
        user = await bot.fetch_user(int(action.target_user_id))
        if not user:
            return ActionResult(action=action, success=False, error=f"User {action.target_user_id} not found")
        
        # Create DM channel first to check if we can reach them
        try:
            dm_channel = await user.create_dm()
        except discord.Forbidden:
            logger.warning(f"[DailyLife] Cannot DM user {action.target_user_id} (DMs disabled)")
            return ActionResult(action=action, success=False, error="User has DMs disabled")
        
        # Use ConversationService for unified processing
        from src_v2.core.conversation import conversation_service, ConversationContext
        
        # Frame the reach-out as a proactive message
        reach_out_prompt = (
            f"[PROACTIVE REACH-OUT] You haven't heard from {user.display_name} in a while. "
            f"Reason: {action.reason}. "
            "Write a warm, non-intrusive message to check in on them."
        )
        
        context = ConversationContext(
            user_id=str(user.id),
            user_name=user.display_name,
            character_name=character.name,
            user_message=reach_out_prompt,
            channel_id=str(dm_channel.id),
            channel_name="DM",
            server_id=None,  # DMs have no server
            message_id=None,  # No triggering message
            is_cross_bot=False,
            origin="daily_life_reach_out",
        )
        
        # Callback to send the DM
        async def send_dm(text: str):
            return await dm_channel.send(text)
        
        result = await conversation_service.process_turn(
            context=context,
            character=character,
            send_callback=send_dm,
        )
        
        if not result.success:
            return ActionResult(action=action, success=False, error=result.error or "Response generation failed")
        
        logger.info(f"[DailyLife] Executed: reach_out to {user.display_name}")
        
        return ActionResult(
            action=action,
            success=True,
            message_id=result.response_message_id,
        )
        
    except discord.Forbidden:
        logger.warning(f"[DailyLife] Cannot DM user {action.target_user_id} (DMs disabled)")
        return ActionResult(action=action, success=False, error="User has DMs disabled")
    except Exception as e:
        logger.error(f"[DailyLife] Reach out failed: {e}")
        return ActionResult(action=action, success=False, error=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# INTERNAL LIFE ACTIONS
# ──────────────────────────────────────────────────────────────────────────────

async def execute_write_diary(
    action: PlannedAction,
    character: "Character",
) -> ActionResult:
    """Generate a diary entry using DiaryGraph."""
    
    try:
        from src_v2.workers.tasks.diary_tasks import run_diary_generation
        
        # Run diary generation directly (not via queue, since we're already in worker context)
        result = await run_diary_generation({}, character.name)
        
        if result.get("success"):
            logger.info(f"[DailyLife] Executed: write_diary (artifact created)")
            return ActionResult(
                action=action,
                success=True,
                artifact_id=result.get("point_id") or result.get("artifact_id"),
            )
        else:
            return ActionResult(
                action=action,
                success=False,
                error=result.get("error", "Diary generation returned failure"),
            )
        
    except Exception as e:
        logger.error(f"[DailyLife] Write diary failed: {e}")
        return ActionResult(action=action, success=False, error=str(e))


async def execute_generate_dream(
    action: PlannedAction,
    character: "Character",
) -> ActionResult:
    """Generate a dream using DreamGraph."""
    
    try:
        from src_v2.workers.tasks.dream_tasks import run_dream_generation
        
        result = await run_dream_generation({}, character.name)
        
        if result.get("success"):
            logger.info(f"[DailyLife] Executed: generate_dream (artifact created)")
            return ActionResult(
                action=action,
                success=True,
                artifact_id=result.get("point_id") or result.get("artifact_id"),
            )
        else:
            return ActionResult(
                action=action,
                success=False,
                error=result.get("error", "Dream generation returned failure"),
            )
        
    except Exception as e:
        logger.error(f"[DailyLife] Generate dream failed: {e}")
        return ActionResult(action=action, success=False, error=str(e))


async def execute_review_goals(
    action: PlannedAction,
    character: "Character",
) -> ActionResult:
    """Review and update goals using GoalStrategist."""
    
    try:
        from src_v2.workers.strategist import run_goal_strategist
        
        result = await run_goal_strategist({}, character.name)
        
        if result.get("success"):
            logger.info(f"[DailyLife] Executed: review_goals")
            return ActionResult(
                action=action,
                success=True,
                artifact_id=result.get("point_id") or result.get("artifact_id"),
            )
        else:
            return ActionResult(
                action=action,
                success=False,
                error=result.get("error", "Goal review returned failure"),
            )
        
    except Exception as e:
        logger.error(f"[DailyLife] Review goals failed: {e}")
        return ActionResult(action=action, success=False, error=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTE FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

async def execute_action(
    state: DailyLifeState,
    bot: commands.Bot,
    character: "Character",
) -> Dict[str, Any]:
    """
    Act phase: Execute the next planned action.
    
    Returns dict with updated executed_actions and current_action_index.
    """
    
    planned = state.get("planned_actions", [])
    current_idx = state.get("current_action_index", 0)
    executed = list(state.get("executed_actions", []))
    
    if current_idx >= len(planned):
        # All actions done
        return {
            "current_action_index": current_idx,
            "executed_actions": executed,
        }
    
    action = planned[current_idx]
    
    # Skip action - no execution needed
    if action.action_type == "skip":
        # No need to mark anything - gather_context already won't call LLM if should_skip=True
        # And if LLM returns skip, those messages are simply "not interesting" right now
        result = ActionResult(action=action, success=True)
        executed.append(result)
        return {
            "current_action_index": current_idx + 1,
            "executed_actions": executed,
        }
    
    # Execute based on action type
    result: ActionResult
    
    if action.action_type == "reply":
        result = await execute_reply(action, bot, character, state)
    elif action.action_type == "react":
        result = await execute_react(action, bot)
    elif action.action_type == "post":
        result = await execute_post(action, bot, character)
    elif action.action_type == "reach_out":
        result = await execute_reach_out(action, bot, character)
    elif action.action_type == "write_diary":
        result = await execute_write_diary(action, character)
    elif action.action_type == "generate_dream":
        result = await execute_generate_dream(action, character)
    elif action.action_type == "review_goals":
        result = await execute_review_goals(action, character)
    else:
        logger.warning(f"[DailyLife] Unknown action type: {action.action_type}")
        result = ActionResult(action=action, success=False, error=f"Unknown action type: {action.action_type}")
    
    executed.append(result)
    
    # Log result
    if result.success:
        logger.info(f"[DailyLife] → {action.action_type}: success")
    else:
        logger.warning(f"[DailyLife] → {action.action_type}: failed - {result.error}")
    
    return {
        "current_action_index": current_idx + 1,
        "executed_actions": executed,
    }
