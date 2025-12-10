"""
Plan node - Decide phase of the stigmergic loop.

LLM reasons about what to do based on gathered context.
Decides WHAT to do, not WHAT TO SAY - content is generated during execution.
"""

from typing import List, Dict, Any, TYPE_CHECKING
from loguru import logger
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage, SystemMessage

from src_v2.agents.daily_life.state import (
    DailyLifeState,
    PlannedAction,
    ChannelState,
    ScoredMessage,
    ConcerningAbsence,
    format_time_ago,
)
from src_v2.agents.llm_factory import create_llm
from src_v2.config.settings import settings

if TYPE_CHECKING:
    from src_v2.core.character import Character


# ──────────────────────────────────────────────────────────────────────────────
# STRUCTURED OUTPUT
# ──────────────────────────────────────────────────────────────────────────────

class PlannedActionSchema(BaseModel):
    """Schema for LLM action output."""
    action_type: str = Field(description="One of: reply, react, post, reach_out, write_diary, generate_dream, review_goals, skip")
    channel_id: str | None = Field(default=None, description="Channel ID for Discord actions")
    target_message_id: str | None = Field(default=None, description="Message ID for reply/react")
    target_user_id: str | None = Field(default=None, description="User ID for reach_out")
    target_bot_name: str | None = Field(default=None, description="Name of another bot to mention (for post actions)")
    emoji: str | None = Field(default=None, description="Emoji for react action")
    reason: str = Field(description="Brief explanation of why this action")
    priority: int = Field(default=10, description="Priority (lower = higher priority)")


class ActionPlan(BaseModel):
    """Schema for the full action plan."""
    actions: List[PlannedActionSchema] = Field(description="List of 0-3 actions to take")


# ──────────────────────────────────────────────────────────────────────────────
# PROMPT BUILDING
# ──────────────────────────────────────────────────────────────────────────────

def format_mentions(mentions: List[ScoredMessage]) -> str:
    """Format mentions for the prompt."""
    if not mentions:
        return "None - no one has mentioned you or replied to you."
    
    lines = []
    for m in mentions:
        age = format_time_ago((m.created_at.timestamp() - m.created_at.timestamp()) / 60)
        mention_type = "mentioned" if m.is_mention else "replied to you"
        lines.append(
            f"- **{m.author_name}** {mention_type} in #{m.channel_name} ({age}):\n"
            f"  \"{m.content[:200]}{'...' if len(m.content) > 200 else ''}\"\n"
            f"  [msg_id: {m.message_id}, channel_id: {m.channel_id}]"
        )
    return "\n".join(lines)


def format_channel_states(channel_states: List[ChannelState]) -> str:
    """Format channel states for the prompt."""
    if not channel_states:
        return "No channels to monitor."
    
    chain_limit = getattr(settings, "DISCORD_CHECK_CHAIN_LIMIT", 5)
    lines = []
    for cs in channel_states:
        # Skip channels with no activity
        if cs.message_count == 0:
            continue
        
        # Check if at chain limit
        if cs.consecutive_bot_messages >= chain_limit:
            lines.append(f"\n### #{cs.channel_name} 🚫 SKIPPED ({cs.consecutive_bot_messages} bot msgs in a row)")
            continue
        
        human_age = format_time_ago(cs.last_human_message_age_minutes)
        chain_warning = f" ⚠️ {cs.consecutive_bot_messages} bot msgs in a row" if cs.consecutive_bot_messages >= 3 else ""
        
        lines.append(f"\n### #{cs.channel_name}{chain_warning}")
        lines.append(f"Last human: {human_age} | Max relevance: {cs.max_relevance_score:.2f}")
        
        # Show top 5 most relevant messages
        relevant = sorted(cs.scored_messages, key=lambda m: m.relevance_score, reverse=True)[:5]
        for msg in relevant:
            if msg.author_is_bot:
                prefix = "🤖"
            else:
                prefix = "👤"
            lines.append(
                f"  {prefix} [{msg.relevance_score:.2f}] {msg.author_name}: {msg.content[:100]}..."
            )
    
    return "\n".join(lines) if lines else "Channels are quiet."


def format_concerning_absences(absences: List[ConcerningAbsence]) -> str:
    """Format concerning absences for the prompt."""
    if not absences:
        return "None - everyone you care about has been active recently."
    
    lines = []
    for a in absences:
        topic_note = f" (last topic: {a.last_topic})" if a.last_topic else ""
        lines.append(
            f"- **{a.user_name}**: {a.days_absent} days absent, trust={a.relationship_strength:.1f}{topic_note}"
        )
    return "\n".join(lines)


def format_internal_state(state: DailyLifeState) -> str:
    """Format internal state for the prompt."""
    lines = []
    
    # Diary
    if state.get("diary_overdue"):
        last = state.get("last_diary_date", "never")
        lines.append(f"- 📔 Diary: OVERDUE (last: {last})")
    else:
        lines.append("- 📔 Diary: up to date")
    
    # Dreams
    if state.get("dreams_could_generate"):
        lines.append("- 💭 Dreams: could process tonight's experiences")
    else:
        lines.append("- 💭 Dreams: not due")
    
    # Goals
    if state.get("goals_stale"):
        last = state.get("last_goal_review", "never")
        lines.append(f"- 🎯 Goals: STALE (last review: {last})")
    else:
        lines.append("- 🎯 Goals: fresh")
    
    return "\n".join(lines)


def build_plan_prompt(state: DailyLifeState, character: "Character") -> str:
    """Build the planning prompt for the LLM."""
    
    # Get character summary
    char_summary = getattr(character, "purpose", "A thoughtful AI assistant")
    
    # Format sections
    mentions_formatted = format_mentions(state.get("mentions", []))
    channels_formatted = format_channel_states(state.get("channel_states", []))
    absences_formatted = format_concerning_absences(state.get("concerning_absences", []))
    internal_formatted = format_internal_state(state)
    
    return f"""You are {state.get('character_name', 'an AI character')}, living your daily life.

## WHO YOU ARE
{char_summary}

## CURRENT TIME & CONTEXT
It's {state.get('current_time', 'unknown')} ({state.get('time_of_day', 'unknown')}, {state.get('day_of_week', 'unknown')}).

## YOUR INTERNAL STATE
{internal_formatted}

## RELATIONSHIPS THAT CONCERN YOU
{absences_formatted}

## MENTIONS (Highest Priority - People Calling for You)
{mentions_formatted}

## CHANNELS YOU WATCH
{channels_formatted}

## GUIDELINES

### Priority Order
1. **Mentions first** - Always respond to direct mentions (unless already responded)
2. **Internal tasks** - Diary/dreams/goals if overdue and time is appropriate
3. **Concerning relationships** - Reach out to users you haven't heard from
4. **Social engagement** - Reply/react/post if there's something worth engaging with

### Social Guidelines
- **Chain limits** - If you see 5+ consecutive bot messages, skip that channel
- **Recency** - If the last human message was >1 hour ago, the conversation may be stale
- **Don't pile on** - If another bot already responded, you probably don't need to
- **Quality over quantity** - One thoughtful action beats three generic ones
- **Reactions are cheap** - Use them to show you're paying attention

### Internal Life Guidelines
- **Morning** is good for diary (reflect on yesterday)
- **Night** is good for dreams (process the day's experiences)
- **Weekly** is good for goal review
- **Don't force it** - Skip internal tasks if nothing feels meaningful

### It's Okay to Skip
If there's nothing worth doing, skip. You'll check again in a few minutes.
Living well includes knowing when to rest.

## YOUR TASK

Decide what actions to take. You are deciding WHAT to do, not WHAT TO SAY.
Content will be generated by specialized agents with full context.

Available action types:
- "reply" - Reply to a Discord message (requires channel_id, target_message_id)
- "react" - Add emoji reaction (requires channel_id, target_message_id, emoji)
- "post" - Start a new conversation (requires channel_id). Can optionally set target_bot_name to mention another bot.
- "reach_out" - DM a user you're concerned about (requires target_user_id)
- "write_diary" - Generate diary entry for yesterday
- "generate_dream" - Process today's experiences as a dream
- "review_goals" - Review and update your goals
- "skip" - Do nothing this check

Return 0-3 actions, ordered by priority (most important first).
If nothing to do, return a single skip action.
"""


# ──────────────────────────────────────────────────────────────────────────────
# MAIN PLAN FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

async def plan_actions(
    state: DailyLifeState,
    character: "Character",
) -> Dict[str, Any]:
    """
    Decide phase: LLM reasons about priorities and actions.
    
    Returns dict with planned_actions and updated messages.
    """
    
    # If should_skip, don't invoke LLM
    if state.get("should_skip"):
        skip_action = PlannedAction(
            action_type="skip",
            reason="Nothing relevant to act on",
            priority=0,
        )
        return {
            "planned_actions": [skip_action],
            "messages": [],
        }
        
    # Safety check: if time_of_day is unknown, gather failed - skip
    if state.get("time_of_day") == "unknown":
        logger.warning("[DailyLife] Skipping planning because gather failed (time_of_day unknown)")
        skip_action = PlannedAction(
            action_type="skip",
            reason="Gather failed (unknown time)",
            priority=0,
        )
        return {
            "planned_actions": [skip_action],
            "messages": [],
        }
    
    # Build prompt
    prompt = build_plan_prompt(state, character)
    
    # Create LLM with structured output
    # Use router model (gemini-flash-lite) - planning is structured output, doesn't need heavy model
    llm = create_llm(temperature=0.3, mode="router")
    structured_llm = llm.with_structured_output(ActionPlan)
    
    try:
        logger.info(f"[DailyLife] Invoking LLM for action planning...")
        
        response: ActionPlan = await structured_llm.ainvoke([
            SystemMessage(content="You are a decision-making agent. Analyze the context and decide what actions to take."),
            HumanMessage(content=prompt),
        ])
        
        # Convert to PlannedAction objects
        planned: List[PlannedAction] = []
        for action in response.actions:
            planned.append(PlannedAction(
                action_type=action.action_type,  # type: ignore
                channel_id=action.channel_id,
                target_message_id=action.target_message_id,
                target_user_id=action.target_user_id,
                target_bot_name=action.target_bot_name,
                emoji=action.emoji,
                reason=action.reason,
                priority=action.priority,
            ))
        
        # Sort by priority
        planned.sort(key=lambda a: a.priority)
        
        # Limit to max actions per session
        max_actions = getattr(settings, "DISCORD_CHECK_MAX_ACTIONS_PER_SESSION", 3)
        planned = planned[:max_actions]
        
        logger.info(f"[DailyLife] Plan: {[a.action_type for a in planned]}")
        
        return {
            "planned_actions": planned,
        }
        
    except Exception as e:
        logger.error(f"[DailyLife] Planning failed: {e}")
        # Fallback: skip
        return {
            "planned_actions": [PlannedAction(action_type="skip", reason=f"Planning error: {e}")],
        }
