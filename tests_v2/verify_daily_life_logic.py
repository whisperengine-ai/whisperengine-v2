import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src_v2.agents.daily_life.models import SensorySnapshot, ChannelSnapshot, MessageSnapshot, ActionCommand

# Mock settings before importing graph if possible, or patch it
with patch("src_v2.config.settings.settings") as mock_settings:
    mock_settings.ENABLE_CHANNEL_LURKING = True
    mock_settings.ENABLE_AUTONOMOUS_POSTING = True
    mock_settings.ENABLE_AUTONOMOUS_REPLIES = True
    mock_settings.AUTONOMOUS_POSTING_CHANNEL_ID = "123456789"
    mock_settings.BOT_CONVERSATION_CHANNEL_ID = "123456789"
    mock_settings.AUTONOMOUS_POST_COOLDOWN_MINUTES = 10
    
    from src_v2.agents.daily_life.graph import DailyLifeGraph

async def test_daily_life_logic():
    print("\n🧪 Testing Daily Life Logic (Remote Brain) - Mocked\n")
    
    # 1. Setup & Mocks
    print("1. Initializing Graph with Mocks...")
    
    # Mock EmbeddingService
    mock_embedding = MagicMock()
    mock_embedding.model.embed.return_value = [[0.1] * 384] 
    
    # Mock CharacterManager
    mock_char_mgr = MagicMock()
    mock_char = MagicMock()
    mock_char.name = "elena"
    mock_char.behavior.drives = {"curiosity": 0.8}
    mock_char_mgr.load_character.return_value = mock_char
    
    # Mock LLM (Planner & Executor)
    mock_llm = MagicMock()
    from langchain_core.messages import AIMessage
    
    async def mock_ainvoke(*args, **kwargs):
        prompt = str(args[0])
        if "Decide if you should respond" in prompt:
            # Reactive scenario
            return AIMessage(content='```json\n{"actions": [{"intent": "reply", "target_message_id": "111", "channel_id": "123456789", "reasoning": "Interesting topic"}]}\n```')
        elif "You are posting in a quiet channel" in prompt:
            # Proactive scenario
            return AIMessage(content="This is a proactive post about silence.")
        return AIMessage(content="{}")

    mock_llm.ainvoke.side_effect = mock_ainvoke

    # Initialize Graph and inject mocks
    graph = DailyLifeGraph()
    graph.embedding_service = mock_embedding
    graph.character_manager = mock_char_mgr
    graph.planner_llm = mock_llm
    graph.executor_llm = mock_llm # Use same mock for executor
    
    # Mock MasterGraphAgent (Execution)
    with patch("src_v2.agents.daily_life.graph.master_graph_agent") as mock_master:
        async def mock_run(*args, **kwargs):
            return "This is a generated response."
        mock_master.run = mock_run
        
        # Patch settings again
        with patch("src_v2.agents.daily_life.graph.settings") as settings:
            settings.ENABLE_CHANNEL_LURKING = True
            settings.ENABLE_AUTONOMOUS_POSTING = True
            settings.ENABLE_AUTONOMOUS_REPLIES = True
            settings.AUTONOMOUS_POSTING_CHANNEL_ID = "123456789"
            settings.BOT_CONVERSATION_CHANNEL_ID = "123456789"
            settings.AUTONOMOUS_POST_COOLDOWN_MINUTES = 10
            
            # Patch random
            with patch("src_v2.agents.daily_life.graph.random") as mock_random:
                mock_random.random.return_value = 0.05 
                mock_random.choice.side_effect = lambda x: x[0] if x else None 

                # Patch TrustManager (NEW)
                with patch("src_v2.agents.daily_life.graph.trust_manager") as mock_trust:
                    async def mock_get_trust(*args, **kwargs):
                        return {"level_label": "Friend", "trust_score": 50}
                    mock_trust.get_relationship_level = mock_get_trust

                    # 2. Scenario: Quiet Channel (Expect 'post')
                    print("\n2. Scenario: Quiet Channel (Expect 'post')")
                    snapshot = SensorySnapshot(
                        bot_name="elena",
                        timestamp=datetime.now(timezone.utc),
                        mentions=[],
                        channels=[
                            ChannelSnapshot(
                                channel_id="123456789",
                                channel_name="general",
                                messages=[] # Empty/Quiet
                            )
                        ]
                    )
                    
                    try:
                        print("   Running graph...")
                        result = await graph.run(snapshot)
                        print(f"   Result: {result}")
                        
                        if result and len(result) > 0:
                            cmd = result[0]
                            if cmd.action_type == "post":
                                print("   ✅ SUCCESS: Graph decided to POST.")
                                print(f"   Content: {cmd.content}")
                            else:
                                print(f"   ❌ FAILURE: Graph decided to {cmd.action_type}.")
                        else:
                            print("   ❌ FAILURE: Graph returned no commands.")
                            
                    except Exception as e:
                        print(f"   ❌ Error running graph: {e}")
                        import traceback
                        traceback.print_exc()

                    # 3. Scenario: Active Channel (Expect 'reply')
                    print("\n3. Scenario: Active Channel (Expect 'reply')")
                    snapshot_active = SensorySnapshot(
                        bot_name="elena",
                        timestamp=datetime.now(timezone.utc),
                        mentions=[],
                        channels=[
                            ChannelSnapshot(
                                channel_id="123456789",
                                channel_name="general",
                                messages=[
                                    MessageSnapshot(
                                        id="111",
                                        content="I wonder if Elena is listening?",
                                        author_id="999",
                                        author_name="User",
                                        is_bot=False,
                                        created_at=datetime.now(timezone.utc),
                                        mentions_bot=False,
                                        channel_id="123456789"
                                    )
                                ]
                            )
                        ]
                    )

                    try:
                        print("   Running graph...")
                        result = await graph.run(snapshot_active)
                        print(f"   Result: {result}")
                        
                        if result and len(result) > 0:
                            cmd = result[0]
                            if cmd.action_type == "reply":
                                print("   ✅ SUCCESS: Graph decided to REPLY.")
                                print(f"   Content: {cmd.content}")
                            else:
                                print(f"   ❌ FAILURE: Graph decided to {cmd.action_type}.")
                        else:
                             print("   ⚠️ Graph returned no commands.")

                    except Exception as e:
                        print(f"   ❌ Error running graph: {e}")
                        import traceback
                        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_daily_life_logic())
