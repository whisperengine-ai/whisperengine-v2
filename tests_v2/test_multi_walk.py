import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src_v2.knowledge.walker import GraphWalker, WalkedNode, WalkedEdge, GraphWalkResult, MultiWalkResult, GraphWalkerAgent

class TestMultiCharacterWalk:
    
    def setup_method(self):
        self.walker = GraphWalker()
        
    @pytest.mark.asyncio
    async def test_multi_walk_basic(self):
        """Should walk primary then secondary graphs from shared nodes."""
        # Setup primary result
        topic_node = WalkedNode(id="topic1", label="Topic", name="Ocean")
        primary_result = GraphWalkResult(
            nodes=[topic_node],
            edges=[],
            clusters=[]
        )
        
        # Setup secondary result
        secondary_node = WalkedNode(id="topic2", label="Topic", name="Fish")
        secondary_result = GraphWalkResult(
            nodes=[secondary_node],
            edges=[],
            clusters=[]
        )
        
        # Mock explore
        self.walker.explore = AsyncMock(side_effect=[primary_result, secondary_result])
        
        # Mock TrustManager (not needed for Topic nodes, but good to have)
        with patch('src_v2.knowledge.walker.TrustManager') as MockTrustManager:
            mock_tm = MockTrustManager.return_value
            mock_tm.get_relationship_level = AsyncMock(return_value={"trust_score": 50})
            
            result = await self.walker.multi_character_walk(
                primary_character="elena",
                secondary_characters=["aetheris"],
                seed_ids=["seed1"]
            )
            
            # Verify results
            assert isinstance(result, MultiWalkResult)
            assert len(result.merged_nodes) == 2
            assert "Ocean" in [n.name for n in result.merged_nodes]
            assert "Fish" in [n.name for n in result.merged_nodes]
            
            # Verify calls
            assert self.walker.explore.call_count == 2
            # Second call should use shared node as seed
            call_args = self.walker.explore.call_args_list[1]
            assert call_args.kwargs['seed_ids'] == ["topic1"]
            assert call_args.kwargs['bot_name'] == "aetheris"

    @pytest.mark.asyncio
    async def test_trust_gating_pass(self):
        """Should include User node if trust > 20."""
        # Primary finds a User
        user_node = WalkedNode(id="user1", label="User", name="Mark")
        primary_result = GraphWalkResult(nodes=[user_node], edges=[], clusters=[])
        secondary_result = GraphWalkResult(nodes=[], edges=[], clusters=[])
        
        self.walker.explore = AsyncMock(side_effect=[primary_result, secondary_result])
        
        with patch('src_v2.knowledge.walker.TrustManager') as MockTrustManager:
            mock_tm = MockTrustManager.return_value
            # Trust is high
            mock_tm.get_relationship_level = AsyncMock(return_value={"trust_score": 50})
            
            await self.walker.multi_character_walk(
                primary_character="elena",
                secondary_characters=["aetheris"],
                seed_ids=["seed1"]
            )
            
            # Should have called explore for secondary with user1
            call_args = self.walker.explore.call_args_list[1]
            assert "user1" in call_args.kwargs['seed_ids']

    @pytest.mark.asyncio
    async def test_trust_gating_fail(self):
        """Should exclude User node if trust <= 20."""
        # Primary finds a User
        user_node = WalkedNode(id="user1", label="User", name="Mark")
        primary_result = GraphWalkResult(nodes=[user_node], edges=[], clusters=[])
        
        self.walker.explore = AsyncMock(return_value=primary_result)
        
        with patch('src_v2.knowledge.walker.TrustManager') as MockTrustManager:
            mock_tm = MockTrustManager.return_value
            # Trust is low
            mock_tm.get_relationship_level = AsyncMock(return_value={"trust_score": 10})
            
            await self.walker.multi_character_walk(
                primary_character="elena",
                secondary_characters=["aetheris"],
                seed_ids=["seed1"]
            )
            
            # Should NOT have called explore for secondary (or called with empty seeds if logic allows, but my logic checks `if not gated_seeds: continue`)
            # Since user1 is the only node, gated_seeds will be empty, so explore won't be called for secondary
            assert self.walker.explore.call_count == 1

    @pytest.mark.asyncio
    async def test_merge_logic(self):
        """Should correctly identify shared concepts."""
        # Primary finds Ocean
        node1 = WalkedNode(id="n1", label="Topic", name="Ocean")
        primary_result = GraphWalkResult(nodes=[node1], edges=[], clusters=[])
        
        # Secondary finds Ocean (shared) and Space (new)
        node2 = WalkedNode(id="n1", label="Topic", name="Ocean") # Same ID
        node3 = WalkedNode(id="n2", label="Topic", name="Space")
        secondary_result = GraphWalkResult(nodes=[node2, node3], edges=[], clusters=[])
        
        self.walker.explore = AsyncMock(side_effect=[primary_result, secondary_result])
        
        with patch('src_v2.knowledge.walker.TrustManager'):
            result = await self.walker.multi_character_walk(
                primary_character="elena",
                secondary_characters=["aetheris"],
                seed_ids=["seed1"]
            )
            
            assert len(result.merged_nodes) == 2 # Ocean (deduped) + Space
            assert "Ocean" in result.shared_concepts
            assert "Space" not in result.shared_concepts

class TestGraphWalkerAgentMulti:
    
    @pytest.mark.asyncio
    async def test_explore_multi_character(self):
        """Should orchestrate multi-walk and interpretation."""
        with patch('src_v2.knowledge.walker.create_llm') as mock_create_llm:
            # Mock LLM
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Shared narrative"))
            mock_create_llm.return_value = mock_llm
            
            agent = GraphWalkerAgent("elena")
            
            # Mock walker.multi_character_walk
            mock_result = MultiWalkResult(
                primary_walk=GraphWalkResult([], [], []),
                secondary_walks={},
                merged_nodes=[WalkedNode(id="n1", label="Topic", name="Ocean")],
                merged_edges=[],
                shared_concepts=["Ocean"]
            )
            agent.walker.multi_character_walk = AsyncMock(return_value=mock_result)
            
            result = await agent.explore_multi_character(
                secondary_characters=["aetheris"],
                seed_ids=["seed1"]
            )
            
            assert result.interpretation == "Shared narrative"
            agent.walker.multi_character_walk.assert_called_once()
