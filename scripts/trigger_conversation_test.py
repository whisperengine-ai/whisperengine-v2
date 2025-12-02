#!/usr/bin/env python3
"""
Manual trigger for bot-to-bot conversation testing.

This script simulates what the ActivityOrchestrator does when it detects
a quiet server - it generates an opening message from one bot to another.

Usage:
    python trigger_conversation_test.py [initiator] [target]
    
Examples:
    python trigger_conversation_test.py elena aetheris
    python trigger_conversation_test.py  # Uses elena -> aetheris by default
"""

import asyncio
import sys
import os

# Set bot name for settings loading
os.environ["DISCORD_BOT_NAME"] = sys.argv[1] if len(sys.argv) > 1 else "elena"

from src_v2.agents.conversation_agent import conversation_agent, TopicMatcher
from src_v2.config.settings import settings


async def main():
    initiator = sys.argv[1] if len(sys.argv) > 1 else "elena"
    target = sys.argv[2] if len(sys.argv) > 2 else "aetheris"
    
    print(f"\n🤖 Bot Conversation Test")
    print(f"=" * 50)
    print(f"Initiator: {initiator}")
    print(f"Target: {target}")
    print(f"ENABLE_BOT_CONVERSATIONS: {settings.ENABLE_BOT_CONVERSATIONS}")
    print(f"=" * 50)
    
    # Step 1: Find shared topics
    print(f"\n📋 Finding shared topics between {initiator} and {target}...")
    matcher = TopicMatcher()
    topics = matcher.find_shared_topics(initiator, target)
    
    if not topics:
        print("❌ No shared topics found!")
        return
    
    print(f"Found {len(topics)} shared topics:")
    for i, topic in enumerate(topics[:3], 1):
        print(f"  {i}. {topic.description} (score: {topic.relevance_score:.2f})")
    
    # Step 2: Select best topic
    best_topic = topics[0]
    print(f"\n🎯 Selected topic: {best_topic.description}")
    print(f"   Initiator goal: {best_topic.initiator_goal.description}")
    print(f"   Responder goal: {best_topic.responder_goal.description}")
    
    # Step 3: Generate opener
    print(f"\n✍️  Generating conversation opener...")
    opener = await conversation_agent.generate_opener(initiator, target, best_topic)
    
    if not opener:
        print("❌ Failed to generate opener!")
        return
    
    print(f"\n{'=' * 50}")
    print(f"📨 GENERATED OPENER:")
    print(f"{'=' * 50}")
    print(f"\n{opener.content}\n")
    print(f"{'=' * 50}")
    
    print("\n✅ Test complete!")
    print("\nTo send this in Discord, the bot would:")
    print(f"  1. Find the target channel (general/chat/etc)")
    print(f"  2. Send the message above")
    print(f"  3. {target}'s cross-bot handler would detect the @mention")
    print(f"  4. {target} would generate a response")
    print(f"  5. Continue for up to {settings.BOT_CONVERSATION_MAX_TURNS} turns")


if __name__ == "__main__":
    asyncio.run(main())
