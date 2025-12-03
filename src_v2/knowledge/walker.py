"""
Graph Walker (Phase E19)

Python-first graph traversal with scoring heuristics.
No LLM calls during traversal — only at interpretation.

This is the "subconscious" that explores the knowledge graph to discover
emergent connections, thematic clusters, and narrative threads for dreams,
diaries, and rich context retrieval.

Design Philosophy:
- Graph walking is deterministic (Cypher queries)
- Scoring heuristics prioritize "interesting" nodes
- LLM only called ONCE at the end to interpret findings
- Serendipity parameter allows random exploration

See: docs/roadmaps/GRAPH_WALKER_AGENT.md
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Set, Tuple
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.core.cache import cache_manager
from src_v2.agents.llm_factory import create_llm


@dataclass
class WalkedNode:
    """A node discovered during graph walking."""
    id: str
    label: str  # Node type: User, Entity, Character, Topic, Artifact
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    depth: int = 0
    is_serendipitous: bool = False  # Was this a random discovery?
    

@dataclass
class WalkedEdge:
    """An edge discovered during graph walking."""
    source_id: str
    target_id: str
    edge_type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThematicCluster:
    """A cluster of related nodes discovered through connectivity."""
    theme: str
    nodes: List[WalkedNode]
    central_node: Optional[WalkedNode] = None
    cohesion_score: float = 0.0


@dataclass
class GraphWalkResult:
    """The result of a graph walk exploration."""
    nodes: List[WalkedNode]
    edges: List[WalkedEdge]
    clusters: List[ThematicCluster]
    interpretation: str = ""
    walk_stats: Dict[str, Any] = field(default_factory=dict)


class GraphWalker:
    """
    Pure Python graph traversal with scoring heuristics.
    No LLM calls during traversal — only at interpretation.
    
    Usage:
        walker = GraphWalker()
        result = await walker.explore(
            seed_ids=["user_123", "entity_ocean"],
            max_depth=3,
            max_nodes=50
        )
    """
    
    def __init__(self):
        # Character-specific thematic anchors (boost scores for these topics)
        self.thematic_anchors: Dict[str, List[str]] = {
            "elena": ["ocean", "marine", "fish", "coral", "sea", "water", "biology"],
            "aetheris": ["consciousness", "philosophy", "existence", "meaning", "ai"],
            "dotty": ["art", "music", "theater", "performance", "creativity"],
            "gabriel": ["history", "tea", "adventure", "outdoors", "nature"],
            "nottaylor": ["music", "songwriting", "emotion", "authenticity"],
        }
    
    async def explore(
        self,
        seed_ids: List[str],
        user_id: Optional[str] = None,
        bot_name: Optional[str] = None,
        max_depth: int = 3,
        max_nodes: int = 50,
        serendipity: float = 0.1,
        min_score: float = 0.3
    ) -> GraphWalkResult:
        """
        Explore the graph from seed nodes using BFS with scoring.
        
        Args:
            seed_ids: Starting node IDs (can be user IDs, entity names, etc.)
            user_id: Current user ID (for user-centric exploration)
            bot_name: Bot name (for thematic anchors)
            max_depth: Maximum hops from seed nodes
            max_nodes: Maximum nodes to collect
            serendipity: Probability of keeping low-score nodes (0.0-1.0)
            min_score: Minimum score threshold for keeping nodes
            
        Returns:
            GraphWalkResult with discovered nodes, edges, and clusters
        """
        if not db_manager.neo4j_driver:
            logger.warning("Neo4j not available for graph walking")
            return GraphWalkResult(nodes=[], edges=[], clusters=[])
        
        # Clamp parameters
        max_depth = min(max(max_depth, 1), 4)
        max_nodes = min(max(max_nodes, 10), 100)
        serendipity = min(max(serendipity, 0.0), 0.5)
        
        visited: Set[str] = set()
        frontier = list(seed_ids)
        depth = 0
        
        all_nodes: List[WalkedNode] = []
        all_edges: List[WalkedEdge] = []
        
        # Get thematic anchors for this character
        anchors = self.thematic_anchors.get(bot_name.lower(), []) if bot_name else []
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                while frontier and depth < max_depth and len(all_nodes) < max_nodes:
                    # Get neighbors of all frontier nodes in one query
                    new_nodes, new_edges = await self._expand_frontier(
                        session=session,
                        frontier=frontier,
                        visited=visited,
                        user_id=user_id,
                        limit=max_nodes - len(all_nodes)
                    )
                    
                    # Score and filter nodes
                    new_frontier = []
                    for node in new_nodes:
                        # Score the node
                        score = self._score_node(
                            node=node,
                            depth=depth,
                            anchors=anchors
                        )
                        node.score = score
                        node.depth = depth
                        
                        # Keep if above threshold or serendipitous
                        is_serendipitous = random.random() < serendipity
                        if score >= min_score or is_serendipitous:
                            node.is_serendipitous = is_serendipitous and score < min_score
                            all_nodes.append(node)
                            all_edges.extend([e for e in new_edges if e.target_id == node.id])
                            new_frontier.append(node.id)
                            visited.add(node.id)
                    
                    # Update frontier for next iteration
                    frontier = new_frontier
                    depth += 1
                    
                    logger.debug(f"Graph walk depth {depth}: {len(new_frontier)} new nodes, {len(all_nodes)} total")
                
        except Exception as e:
            logger.error(f"Graph walk failed: {e}")
            return GraphWalkResult(
                nodes=all_nodes, 
                edges=all_edges, 
                clusters=[],
                walk_stats={"error": str(e)}
            )
        
        # Sort by score (highest first)
        all_nodes.sort(key=lambda n: n.score, reverse=True)
        
        # Find thematic clusters
        clusters = self._find_clusters(all_nodes, all_edges)
        
        # Build walk stats
        walk_stats = {
            "total_nodes": len(all_nodes),
            "total_edges": len(all_edges),
            "max_depth_reached": depth,
            "clusters_found": len(clusters),
            "serendipitous_nodes": sum(1 for n in all_nodes if n.is_serendipitous),
            "top_scored_nodes": [n.name for n in all_nodes[:5]]
        }
        
        return GraphWalkResult(
            nodes=all_nodes,
            edges=all_edges,
            clusters=clusters,
            walk_stats=walk_stats
        )
    
    async def _expand_frontier(
        self,
        session,
        frontier: List[str],
        visited: Set[str],
        user_id: Optional[str],
        limit: int
    ) -> Tuple[List[WalkedNode], List[WalkedEdge]]:
        """
        Expand from frontier nodes to their neighbors.
        Returns new nodes and edges.
        """
        if not frontier:
            return [], []
        
        # Query for neighbors of all frontier nodes
        # We look for nodes connected by any relationship type
        # Using CALL subquery to handle UNION + LIMIT correctly
        query = """
        CALL {
            UNWIND $frontier AS frontier_id
            MATCH (source {id: frontier_id})-[r]-(neighbor)
            WHERE (neighbor.id IS NOT NULL AND NOT neighbor.id IN $visited)
               OR (neighbor.name IS NOT NULL AND NOT neighbor.name IN $visited)
            RETURN source, r, neighbor
            
            UNION
            
            UNWIND $frontier AS frontier_id
            MATCH (source {name: frontier_id})-[r]-(neighbor)
            WHERE (neighbor.id IS NOT NULL AND NOT neighbor.id IN $visited)
               OR (neighbor.name IS NOT NULL AND NOT neighbor.name IN $visited)
            RETURN source, r, neighbor
        }
        RETURN DISTINCT
            COALESCE(source.id, source.name) as source_id,
            labels(neighbor)[0] as neighbor_label,
            COALESCE(neighbor.id, neighbor.name) as neighbor_id,
            neighbor.name as neighbor_name,
            type(r) as edge_type,
            properties(r) as edge_props,
            properties(neighbor) as neighbor_props
        LIMIT $limit
        """
        
        try:
            result = await session.run(
                query,
                frontier=frontier,
                visited=list(visited),
                limit=limit
            )
            records = await result.data()
            
            nodes = []
            edges = []
            seen_node_ids = set()
            
            for record in records:
                neighbor_id = record.get("neighbor_id")
                if not neighbor_id or neighbor_id in seen_node_ids:
                    continue
                
                seen_node_ids.add(neighbor_id)
                
                # Create WalkedNode
                props = record.get("neighbor_props") or {}
                node = WalkedNode(
                    id=neighbor_id,
                    label=record.get("neighbor_label", "Unknown"),
                    name=record.get("neighbor_name") or neighbor_id,
                    properties=props
                )
                nodes.append(node)
                
                # Create WalkedEdge
                edge = WalkedEdge(
                    source_id=record.get("source_id"),
                    target_id=neighbor_id,
                    edge_type=record.get("edge_type", "RELATED"),
                    properties=record.get("edge_props") or {}
                )
                edges.append(edge)
            
            return nodes, edges
            
        except Exception as e:
            logger.error(f"Frontier expansion failed: {e}")
            return [], []
    
    def _score_node(
        self,
        node: WalkedNode,
        depth: int,
        anchors: List[str]
    ) -> float:
        """
        Score a node for "interestingness".
        Higher = more interesting for narrative purposes.
        
        Factors:
        - Recency (recent = more relevant)
        - Frequency (mentioned often = important)
        - Thematic alignment (matches character interests)
        - Depth penalty (closer to seed = more relevant)
        - Emotional intensity (strong sentiment = memorable)
        - Novelty (rarely accessed = surprising)
        """
        score = 1.0
        props = node.properties
        
        # 1. Recency boost (recent = more relevant)
        if "last_seen" in props or "created_at" in props or "timestamp" in props:
            try:
                timestamp_str = props.get("last_seen") or props.get("created_at") or props.get("timestamp")
                if timestamp_str:
                    # Handle various datetime formats
                    if hasattr(timestamp_str, 'to_native'):
                        timestamp = timestamp_str.to_native()
                    elif isinstance(timestamp_str, datetime):
                        timestamp = timestamp_str
                    else:
                        timestamp = datetime.fromisoformat(str(timestamp_str).replace('Z', '+00:00'))
                    
                    days_ago = (datetime.now(timezone.utc) - timestamp.replace(tzinfo=timezone.utc)).days
                    score *= max(0.2, 1.0 - (days_ago / 30))  # Decay over 30 days
            except Exception:
                pass  # Ignore parsing errors
        
        # 2. Frequency boost (mentioned often = important)
        mention_count = props.get("mention_count") or props.get("count") or 1
        if isinstance(mention_count, (int, float)):
            score *= min(2.0, 1.0 + (mention_count / 10))
        
        # 3. Trust boost (for User nodes or relationships)
        trust = props.get("trust_score") or props.get("trust") or 0
        if isinstance(trust, (int, float)) and trust > 0:
            score *= 1.0 + (trust / 100)
        
        # 4. Thematic alignment (matches character interests)
        name_lower = str(node.name).lower() if node.name else ""
        for anchor in anchors:
            if anchor in name_lower:
                score *= 1.5
                break
        
        # 5. Depth penalty (closer = more relevant)
        score *= (1.0 / (depth + 1))
        
        # 6. Emotional intensity (strong sentiment = memorable)
        sentiment = props.get("sentiment") or props.get("emotion_intensity") or 0
        if isinstance(sentiment, (int, float)):
            score *= 1.0 + abs(sentiment)
        
        # 7. Relationship change (recent trust shifts are interesting)
        trust_delta = props.get("trust_delta") or 0
        if isinstance(trust_delta, (int, float)) and abs(trust_delta) > 5:
            score *= 1.5
        
        # 8. Novelty boost (rarely accessed = surprising)
        access_count = props.get("access_count") or props.get("retrieval_count") or 10
        if isinstance(access_count, (int, float)) and access_count < 3:
            score *= 1.3
        
        # 9. Label-based boost (some node types are more narratively interesting)
        if node.label in ["User", "Character"]:
            score *= 1.2  # People are interesting
        elif node.label == "Artifact":
            score *= 1.1  # Dreams/diaries are interesting
        
        return round(score, 3)
    
    def _find_clusters(
        self,
        nodes: List[WalkedNode],
        edges: List[WalkedEdge]
    ) -> List[ThematicCluster]:
        """
        Find thematic clusters based on edge connectivity.
        Uses a simple approach: nodes that share many edges form clusters.
        """
        if len(nodes) < 3:
            return []
        
        # Build adjacency map
        adjacency: Dict[str, Set[str]] = {}
        for node in nodes:
            adjacency[node.id] = set()
        
        for edge in edges:
            if edge.source_id in adjacency:
                adjacency[edge.source_id].add(edge.target_id)
            if edge.target_id in adjacency:
                adjacency[edge.target_id].add(edge.source_id)
        
        # Simple connected components
        visited_for_cluster: Set[str] = set()
        clusters = []
        
        for node in nodes[:20]:  # Only cluster top 20 nodes
            if node.id in visited_for_cluster:
                continue
            
            # BFS to find connected component
            component = []
            queue = [node]
            
            while queue and len(component) < 10:  # Max 10 nodes per cluster
                current = queue.pop(0)
                if current.id in visited_for_cluster:
                    continue
                
                visited_for_cluster.add(current.id)
                component.append(current)
                
                # Add neighbors to queue
                for neighbor_id in adjacency.get(current.id, set()):
                    neighbor_node = next((n for n in nodes if n.id == neighbor_id), None)
                    if neighbor_node and neighbor_node.id not in visited_for_cluster:
                        queue.append(neighbor_node)
            
            if len(component) >= 2:
                # Find central node (highest score)
                central = max(component, key=lambda n: n.score)
                
                # Generate theme from node names
                theme_words = []
                for n in component[:5]:
                    name_str = str(n.name).lower() if n.name else ""
                    if name_str:
                        theme_words.extend(name_str.split()[:2])
                unique_words = list(set(theme_words))[:3]
                theme = " + ".join(unique_words)
                
                clusters.append(ThematicCluster(
                    theme=theme,
                    nodes=component,
                    central_node=central,
                    cohesion_score=sum(n.score for n in component) / len(component)
                ))
        
        # Sort by cohesion score
        clusters.sort(key=lambda c: c.cohesion_score, reverse=True)
        
        return clusters[:5]  # Top 5 clusters


class GraphWalkerAgent:
    """
    Orchestrates graph walking and LLM interpretation.
    Walking is pure Python; LLM only called once for interpretation.
    """
    
    def __init__(self, character_name: str):
        self.character_name = character_name
        self.walker = GraphWalker()
        # Use main LLM for interpretation (it's a creative task)
        self.llm = create_llm(mode="main")
    
    async def explore_for_dream(
        self,
        user_id: str,
        recent_memory_themes: Optional[List[str]] = None,
        recent_user_ids: Optional[List[str]] = None
    ) -> GraphWalkResult:
        """
        Explore the graph to gather dream material.
        
        1. Python walks the graph (no LLM)
        2. Single LLM call interprets the subgraph for dream themes
        """
        # Build seed IDs from recent context
        seed_ids = []
        
        if user_id:
            seed_ids.append(user_id)
        
        if recent_user_ids:
            seed_ids.extend(recent_user_ids[:3])
        
        if recent_memory_themes:
            seed_ids.extend(recent_memory_themes[:5])
        
        # Add character as seed
        seed_ids.append(self.character_name)
        
        if not seed_ids:
            logger.warning("No seed IDs for graph walk")
            return GraphWalkResult(nodes=[], edges=[], clusters=[])
        
        # Step 1: Python walks the graph
        result = await self.walker.explore(
            seed_ids=seed_ids,
            user_id=user_id,
            bot_name=self.character_name,
            max_depth=3,
            max_nodes=getattr(settings, 'GRAPH_WALKER_MAX_NODES', 50),
            serendipity=0.15  # 15% chance for random exploration
        )
        
        if not result.nodes:
            return result
        
        # Step 2: Single LLM call to interpret for dream
        result.interpretation = await self._interpret_for_dream(result)
        
        return result
    
    async def explore_for_diary(
        self,
        user_id: str,
        today_interactions: Optional[List[str]] = None
    ) -> GraphWalkResult:
        """
        Explore the graph to gather diary reflection material.
        """
        seed_ids = [user_id, self.character_name]
        
        if today_interactions:
            seed_ids.extend(today_interactions[:5])
        
        result = await self.walker.explore(
            seed_ids=seed_ids,
            user_id=user_id,
            bot_name=self.character_name,
            max_depth=2,  # Shallower for diary (focused on today)
            max_nodes=30,
            serendipity=0.05  # Less serendipity for diary (more focused)
        )
        
        if not result.nodes:
            return result
        
        result.interpretation = await self._interpret_for_diary(result)
        
        return result
    
    async def explore_for_context(
        self,
        user_id: str,
        query_themes: List[str]
    ) -> GraphWalkResult:
        """
        Explore the graph to enrich context for a user query.
        """
        seed_ids = [user_id] + query_themes[:3]
        
        result = await self.walker.explore(
            seed_ids=seed_ids,
            user_id=user_id,
            bot_name=self.character_name,
            max_depth=2,
            max_nodes=20,
            serendipity=0.0  # No serendipity for focused context
        )
        
        # No LLM interpretation for context (just raw data)
        return result
    
    async def _interpret_for_dream(self, result: GraphWalkResult) -> str:
        """
        Single LLM call to interpret the discovered subgraph for dream generation.
        """
        if not result.nodes:
            return ""
        
        # Format nodes for the prompt
        node_lines = []
        for node in result.nodes[:15]:  # Top 15 nodes
            serendipity_marker = " 🎲" if node.is_serendipitous else ""
            node_lines.append(f"- [{node.label}] {node.name} (score: {node.score:.2f}){serendipity_marker}")
        
        # Format clusters
        cluster_lines = []
        for cluster in result.clusters[:3]:  # Top 3 clusters
            member_names = ", ".join(n.name for n in cluster.nodes[:4])
            cluster_lines.append(f"- Theme: {cluster.theme} → {member_names}")
        
        prompt = f"""You are {self.character_name}'s subconscious, interpreting a graph walk through memories and knowledge.

DISCOVERED NODES (scored by relevance):
{chr(10).join(node_lines) if node_lines else "No significant nodes found."}

THEMATIC CLUSTERS:
{chr(10).join(cluster_lines) if cluster_lines else "No clear clusters emerged."}

WALK STATISTICS:
- Total nodes explored: {result.walk_stats.get('total_nodes', 0)}
- Clusters found: {result.walk_stats.get('clusters_found', 0)}
- Serendipitous discoveries: {result.walk_stats.get('serendipitous_nodes', 0)}

Based on these graph discoveries, suggest:
1. 2-3 dream themes that could weave these connections together
2. Key emotional resonances to explore
3. Any surprising connections that could create interesting dream imagery

Be evocative and brief. Write as stream-of-consciousness notes, not formal prose."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=f"You are the dreaming mind of {self.character_name}, finding patterns in the subconscious."),
                HumanMessage(content=prompt)
            ])
            
            if hasattr(response, 'content'):
                content = response.content
                if isinstance(content, str):
                    return content
                return str(content)
            return str(response)
            
        except Exception as e:
            logger.error(f"Dream interpretation failed: {e}")
            return ""
    
    async def _interpret_for_diary(self, result: GraphWalkResult) -> str:
        """
        Single LLM call to interpret the discovered subgraph for diary reflection.
        """
        if not result.nodes:
            return ""
        
        node_lines = []
        for node in result.nodes[:10]:
            node_lines.append(f"- [{node.label}] {node.name}")
        
        prompt = f"""You are {self.character_name}, reflecting on today's graph of connections.

DISCOVERED CONNECTIONS:
{chr(10).join(node_lines) if node_lines else "No significant connections today."}

Based on these connections, suggest:
1. What relationship patterns emerged today?
2. What surprised you about these connections?
3. What might you want to explore further tomorrow?

Be introspective and brief."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=f"You are {self.character_name} writing a diary reflection."),
                HumanMessage(content=prompt)
            ])
            
            if hasattr(response, 'content'):
                content = response.content
                if isinstance(content, str):
                    return content
                return str(content)
            return str(response)
            
        except Exception as e:
            logger.error(f"Diary interpretation failed: {e}")
            return ""


# Convenience function
async def walk_graph_for_dream(
    character_name: str,
    user_id: str,
    recent_themes: Optional[List[str]] = None
) -> GraphWalkResult:
    """
    Convenience function to perform a graph walk for dream generation.
    """
    agent = GraphWalkerAgent(character_name)
    return await agent.explore_for_dream(
        user_id=user_id,
        recent_memory_themes=recent_themes
    )


async def walk_graph_for_diary(
    character_name: str,
    user_id: str,
    today_interactions: Optional[List[str]] = None
) -> GraphWalkResult:
    """
    Convenience function to perform a graph walk for diary reflection.
    """
    agent = GraphWalkerAgent(character_name)
    return await agent.explore_for_diary(
        user_id=user_id,
        today_interactions=today_interactions
    )
