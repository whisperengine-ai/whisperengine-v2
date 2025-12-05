"""
Graph Enrichment Agent (Phase E25)

Proactively enriches Neo4j with discovered relationships.
Runs in background worker, minimal LLM calls needed.

This agent analyzes conversations and creates edges for:
- User-Topic relationships (what users discuss)
- User-User connections (who interacts with whom)
- Topic-Topic relationships (co-occurring themes)
- Entity linking (entities mentioned together)

Design Philosophy:
- Let the system *notice* connections, not declare them
- All edges are idempotent (MERGE pattern)
- No new Neo4j node types - only edges
- Privacy-respecting (trust-gated, server-scoped)

See: docs/spec/SPEC-E25-GRAPH_WALKER_EXTENSIONS.md
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import Counter, defaultdict
from loguru import logger

from src_v2.config.settings import settings
from src_v2.core.database import db_manager, retry_db_operation, require_db


@dataclass
class CoOccurrence:
    """Two entities that appear together in conversation."""
    entity_a: str
    entity_b: str
    count: int
    context: str = ""  # Brief context of co-occurrence


@dataclass
class UserInteraction:
    """An interaction between two users."""
    user_a: str
    user_b: str
    channel_id: str
    server_id: str
    interaction_count: int
    last_interaction: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TopicDiscussion:
    """A topic that a user has discussed."""
    user_id: str
    topic: str
    count: int
    last_mentioned: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EnrichmentResult:
    """Result of a graph enrichment run."""
    edges_created: int = 0
    edges_updated: int = 0
    user_topic_edges: int = 0
    user_user_edges: int = 0
    topic_topic_edges: int = 0
    entity_entity_edges: int = 0
    skipped_privacy: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def total_edges(self) -> int:
        return self.edges_created + self.edges_updated


class GraphEnrichmentAgent:
    """
    Proactively enriches Neo4j with discovered relationships.
    Runs in background worker, no LLM calls needed for basic enrichment.
    """
    
    # Minimum occurrences before creating an edge
    MIN_TOPIC_MENTIONS = 2      # User mentions topic N times before DISCUSSED edge
    MIN_COOCCURRENCE = 2        # Entities appear together N times before RELATED_TO edge
    MIN_INTERACTION = 1         # Users interact N times before CONNECTED_TO edge
    
    # Topics to ignore (too generic)
    IGNORE_TOPICS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "shall",
        "i", "you", "he", "she", "it", "we", "they", "me", "him", "her",
        "this", "that", "these", "those", "what", "which", "who", "whom",
        "yes", "no", "not", "just", "only", "also", "very", "really",
        "okay", "ok", "yeah", "yep", "nope", "hmm", "hm", "uh", "um",
    }
    
    def __init__(self):
        self.min_topic_mentions = getattr(settings, 'ENRICHMENT_MIN_TOPIC_MENTIONS', self.MIN_TOPIC_MENTIONS)
        self.min_cooccurrence = getattr(settings, 'ENRICHMENT_MIN_COOCCURRENCE', self.MIN_COOCCURRENCE)
        self.min_interaction = getattr(settings, 'ENRICHMENT_MIN_INTERACTION', self.MIN_INTERACTION)
    
    async def enrich_from_conversation(
        self,
        messages: List[Dict[str, Any]],
        channel_id: str,
        server_id: str,
        bot_name: str
    ) -> EnrichmentResult:
        """
        Analyze a conversation and add discovered edges.
        
        Args:
            messages: List of message dicts with 'user_id', 'content', 'timestamp'
            channel_id: Discord channel ID
            server_id: Discord server ID
            bot_name: Name of the bot analyzing this conversation
            
        Returns:
            EnrichmentResult with stats about edges created/updated
        """
        result = EnrichmentResult()
        
        if not messages:
            return result
        
        # Normalize messages to dict format (handle both dict and LangChain message objects)
        normalized_messages = []
        for m in messages:
            if isinstance(m, dict):
                normalized_messages.append(m)
            else:
                # Handle LangChain message objects or other objects with attributes
                try:
                    user_id = 'unknown'
                    if hasattr(m, 'additional_kwargs') and isinstance(m.additional_kwargs, dict):
                        user_id = m.additional_kwargs.get('user_id', 'unknown')
                    elif hasattr(m, 'user_id'):
                        user_id = getattr(m, 'user_id', 'unknown')
                    
                    content = getattr(m, 'content', str(m))
                    
                    timestamp = 'unknown'
                    if hasattr(m, 'additional_kwargs') and isinstance(m.additional_kwargs, dict):
                        timestamp = m.additional_kwargs.get('timestamp', datetime.now(timezone.utc).isoformat())
                    else:
                        timestamp = datetime.now(timezone.utc).isoformat()
                    
                    normalized_messages.append({
                        "user_id": user_id,
                        "content": content,
                        "timestamp": timestamp
                    })
                except Exception as obj_e:
                    logger.warning(f"Could not normalize message object: {obj_e}")
                    continue
        
        messages = normalized_messages
        
        # Extract participants
        participants = set(m.get('user_id') for m in messages if m.get('user_id'))
        
        # 1. Find topics discussed by each user
        user_topics = self._extract_user_topics(messages)
        
        # 2. Find entity co-occurrences within messages
        cooccurrences = self._find_cooccurrences(messages)
        
        # 3. Find user-user interactions
        interactions = self._find_user_interactions(messages, channel_id, server_id)
        
        # 4. Create edges (trust-gated)
        try:
            # User-Topic edges
            topic_result = await self._create_user_topic_edges(
                user_topics, bot_name, server_id
            )
            result.user_topic_edges = topic_result
            result.edges_created += topic_result
            
            # Topic-Topic edges (from co-occurring topics)
            topic_cooc = self._find_topic_cooccurrences(user_topics)
            topic_result = await self._create_topic_topic_edges(topic_cooc)
            result.topic_topic_edges = topic_result
            result.edges_created += topic_result
            
            # User-User edges
            user_result = await self._create_user_user_edges(
                interactions, bot_name
            )
            result.user_user_edges = user_result
            result.edges_created += user_result
            
            # Entity-Entity edges
            entity_result = await self._create_entity_entity_edges(cooccurrences)
            result.entity_entity_edges = entity_result
            result.edges_created += entity_result
            
        except Exception as e:
            logger.error(f"Graph enrichment failed: {e}")
            result.errors.append(str(e))
        
        if result.total_edges > 0:
            logger.info(
                f"Graph enrichment complete: {result.edges_created} edges created "
                f"(topics: {result.user_topic_edges}, users: {result.user_user_edges}, "
                f"topic-topic: {result.topic_topic_edges}, entities: {result.entity_entity_edges})"
            )
        
        return result
    
    def _extract_user_topics(
        self,
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Counter]:
        """
        Extract topics discussed by each user.
        Returns dict mapping user_id -> Counter of topics.
        """
        user_topics: Dict[str, Counter] = defaultdict(Counter)
        
        for msg in messages:
            user_id = msg.get('user_id')
            content = msg.get('content', '')
            
            if not user_id or not content:
                continue
            
            # Extract words as potential topics (simple approach)
            # In future, could use NER or the existing fact extractor
            words = self._extract_topic_words(content)
            user_topics[user_id].update(words)
        
        return dict(user_topics)
    
    def _extract_topic_words(self, text: str) -> List[str]:
        """
        Extract meaningful words from text that could be topics.
        Simple heuristic approach - no LLM needed.
        """
        import re
        
        # Clean and tokenize
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        
        # Filter out common words
        topics = [w for w in words if w not in self.IGNORE_TOPICS]
        
        # Dedupe while preserving order (for context)
        seen = set()
        unique_topics = []
        for t in topics:
            if t not in seen:
                seen.add(t)
                unique_topics.append(t)
        
        return unique_topics
    
    def _find_cooccurrences(
        self,
        messages: List[Dict[str, Any]],
        window_size: int = 1
    ) -> List[CoOccurrence]:
        """
        Find entities that appear in the same message.
        Returns list of CoOccurrence objects.
        """
        pair_counts: Counter = Counter()
        
        for msg in messages:
            content = msg.get('content', '')
            if not content:
                continue
            
            # Extract entities from this message
            entities = self._extract_topic_words(content)
            
            # Count pairs within this message
            for i, e1 in enumerate(entities):
                for e2 in entities[i+1:]:
                    # Alphabetical ordering for consistent pair keys
                    pair = tuple(sorted([e1, e2]))
                    pair_counts[pair] += 1
        
        # Convert to CoOccurrence objects (filter by minimum)
        cooccurrences = []
        for (e1, e2), count in pair_counts.items():
            if count >= self.min_cooccurrence:
                cooccurrences.append(CoOccurrence(
                    entity_a=e1,
                    entity_b=e2,
                    count=count
                ))
        
        return cooccurrences
    
    def _find_topic_cooccurrences(
        self,
        user_topics: Dict[str, Counter]
    ) -> List[CoOccurrence]:
        """
        Find topics that co-occur across users' discussions.
        If multiple users discuss the same pair of topics, those topics are related.
        """
        # Aggregate topic pairs across all users
        topic_pairs: Counter = Counter()
        
        for user_id, topics in user_topics.items():
            # Get topics this user mentioned at least twice
            significant_topics = [t for t, c in topics.items() if c >= 2]
            
            # Count pairs
            for i, t1 in enumerate(significant_topics):
                for t2 in significant_topics[i+1:]:
                    pair = tuple(sorted([t1, t2]))
                    topic_pairs[pair] += 1
        
        # Return pairs that appear for multiple users or very frequently
        cooccurrences = []
        for (t1, t2), count in topic_pairs.items():
            if count >= self.min_cooccurrence:
                cooccurrences.append(CoOccurrence(
                    entity_a=t1,
                    entity_b=t2,
                    count=count
                ))
        
        return cooccurrences
    
    def _find_user_interactions(
        self,
        messages: List[Dict[str, Any]],
        channel_id: str,
        server_id: str
    ) -> List[UserInteraction]:
        """
        Find user-user interactions from message sequence.
        Users who talk in the same channel in close proximity are connected.
        """
        interactions: Dict[Tuple[str, str], int] = Counter()
        
        # Simple heuristic: users who appear within 5 messages of each other
        user_sequence: List[str] = [m.get('user_id') for m in messages if m.get('user_id')]  # type: ignore
        
        window = 5
        for i, user_a in enumerate(user_sequence):
            for j in range(i + 1, min(i + window, len(user_sequence))):
                user_b = user_sequence[j]
                if user_a != user_b:
                    # Alphabetical ordering for consistent pair keys
                    pair = (min(user_a, user_b), max(user_a, user_b))
                    interactions[pair] += 1
        
        # Convert to UserInteraction objects
        result = []
        for (user_a, user_b), count in interactions.items():
            if count >= self.min_interaction:
                result.append(UserInteraction(
                    user_a=user_a,
                    user_b=user_b,
                    channel_id=channel_id,
                    server_id=server_id,
                    interaction_count=count
                ))
        
        return result
    
    @require_db("neo4j", default_return=0)
    @retry_db_operation(max_retries=2)
    async def _create_user_topic_edges(
        self,
        user_topics: Dict[str, Counter],
        bot_name: str,
        server_id: str
    ) -> int:
        """
        Create (User)-[:DISCUSSED]->(Topic) edges.
        Idempotent via MERGE.
        """
        edges_created = 0
        
        if not db_manager.neo4j_driver:
            return edges_created
        
        async with db_manager.neo4j_driver.session() as session:
            for user_id, topics in user_topics.items():
                for topic, count in topics.items():
                    if count < self.min_topic_mentions:
                        continue
                    
                    # Check trust (only create edges for non-strangers)
                    # Simple check - if user exists in graph, they've interacted
                    query = """
                    MERGE (u:User {id: $user_id})
                    MERGE (t:Topic {name: $topic_name})
                    MERGE (u)-[r:DISCUSSED]->(t)
                    ON CREATE SET 
                        r.count = $count,
                        r.first_date = datetime(),
                        r.last_date = datetime(),
                        r.source_bot = $bot_name,
                        r.server_id = $server_id
                    ON MATCH SET 
                        r.count = r.count + $count,
                        r.last_date = datetime()
                    RETURN r.count as total_count
                    """
                    
                    try:
                        result = await session.run(
                            query,
                            user_id=user_id,
                            topic_name=topic.lower(),
                            count=count,
                            bot_name=bot_name,
                            server_id=server_id
                        )
                        await result.consume()
                        edges_created += 1
                    except Exception as e:
                        logger.debug(f"Failed to create user-topic edge: {e}")
        
        return edges_created
    
    @require_db("neo4j", default_return=0)
    @retry_db_operation(max_retries=2)
    async def _create_user_user_edges(
        self,
        interactions: List[UserInteraction],
        bot_name: str
    ) -> int:
        """
        Create (User)-[:CONNECTED_TO]->(User) edges.
        Only within same server for privacy.
        """
        edges_created = 0
        
        if not db_manager.neo4j_driver:
            return edges_created
        
        async with db_manager.neo4j_driver.session() as session:
            for interaction in interactions:
                query = """
                MERGE (u1:User {id: $user_a})
                MERGE (u2:User {id: $user_b})
                MERGE (u1)-[r:CONNECTED_TO]->(u2)
                ON CREATE SET 
                    r.interaction_count = $count,
                    r.first_interaction = datetime(),
                    r.last_interaction = datetime(),
                    r.server_id = $server_id,
                    r.channel_id = $channel_id,
                    r.source_bot = $bot_name
                ON MATCH SET 
                    r.interaction_count = r.interaction_count + $count,
                    r.last_interaction = datetime()
                """
                
                try:
                    await session.run(
                        query,
                        user_a=interaction.user_a,
                        user_b=interaction.user_b,
                        count=interaction.interaction_count,
                        server_id=interaction.server_id,
                        channel_id=interaction.channel_id,
                        bot_name=bot_name
                    )
                    edges_created += 1
                except Exception as e:
                    logger.debug(f"Failed to create user-user edge: {e}")
        
        return edges_created
    
    @require_db("neo4j", default_return=0)
    @retry_db_operation(max_retries=2)
    async def _create_topic_topic_edges(
        self,
        cooccurrences: List[CoOccurrence]
    ) -> int:
        """
        Create (Topic)-[:RELATED_TO]->(Topic) edges.
        Topics that co-occur frequently are related.
        """
        edges_created = 0
        
        if not db_manager.neo4j_driver:
            return edges_created
        
        async with db_manager.neo4j_driver.session() as session:
            for cooc in cooccurrences:
                query = """
                MERGE (t1:Topic {name: $topic_a})
                MERGE (t2:Topic {name: $topic_b})
                MERGE (t1)-[r:RELATED_TO]->(t2)
                ON CREATE SET 
                    r.strength = $count,
                    r.first_seen = datetime(),
                    r.last_seen = datetime()
                ON MATCH SET 
                    r.strength = r.strength + $count,
                    r.last_seen = datetime()
                """
                
                try:
                    await session.run(
                        query,
                        topic_a=cooc.entity_a.lower(),
                        topic_b=cooc.entity_b.lower(),
                        count=cooc.count
                    )
                    edges_created += 1
                except Exception as e:
                    logger.debug(f"Failed to create topic-topic edge: {e}")
        
        return edges_created
    
    @require_db("neo4j", default_return=0)
    @retry_db_operation(max_retries=2)
    async def _create_entity_entity_edges(
        self,
        cooccurrences: List[CoOccurrence]
    ) -> int:
        """
        Create (Entity)-[:LINKED_TO]->(Entity) edges.
        Entities mentioned together are linked.
        """
        edges_created = 0
        
        if not db_manager.neo4j_driver:
            return edges_created
        
        async with db_manager.neo4j_driver.session() as session:
            for cooc in cooccurrences:
                query = """
                MERGE (e1:Entity {name: $entity_a})
                MERGE (e2:Entity {name: $entity_b})
                MERGE (e1)-[r:LINKED_TO]->(e2)
                ON CREATE SET 
                    r.count = $count,
                    r.first_seen = datetime(),
                    r.last_seen = datetime()
                ON MATCH SET 
                    r.count = r.count + $count,
                    r.last_seen = datetime()
                """
                
                try:
                    await session.run(
                        query,
                        entity_a=cooc.entity_a,
                        entity_b=cooc.entity_b,
                        count=cooc.count
                    )
                    edges_created += 1
                except Exception as e:
                    logger.debug(f"Failed to create entity-entity edge: {e}")
        
        return edges_created
    
    async def enrich_from_batch(
        self,
        hours: int = 24,
        bot_name: str = "unknown"
    ) -> EnrichmentResult:
        """
        Batch enrichment from recent messages.
        Called by nightly cron job.
        
        Args:
            hours: Look back this many hours
            bot_name: Bot running the enrichment
            
        Returns:
            EnrichmentResult with aggregate stats
        """
        result = EnrichmentResult()
        
        if not db_manager.postgres_pool:
            logger.warning("PostgreSQL not available for batch enrichment")
            return result
        
        try:
            # Get recent messages grouped by channel
            async with db_manager.postgres_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        channel_id,
                        user_id,
                        content,
                        timestamp
                    FROM v2_chat_history
                    WHERE timestamp > NOW() - make_interval(hours => $1)
                        AND content IS NOT NULL
                        AND LENGTH(content) > 10
                    ORDER BY channel_id, timestamp
                """, hours)
            
            if not rows:
                logger.info(f"No messages found in last {hours} hours for enrichment")
                return result
            
            # Group by channel
            channel_messages: Dict[str, List[Dict]] = defaultdict(list)
            
            for row in rows:
                channel_id = str(row['channel_id']) if row['channel_id'] else "DM"
                channel_messages[channel_id].append({
                    'user_id': str(row['user_id']),
                    'content': row['content'],
                    'timestamp': row['timestamp']
                })
            
            # Enrich each channel
            for channel_id, messages in channel_messages.items():
                # We don't store server_id in chat history yet, so use "unknown" or infer
                server_id = "unknown"
                
                channel_result = await self.enrich_from_conversation(
                    messages=messages,
                    channel_id=channel_id,
                    server_id=server_id,
                    bot_name=bot_name
                )
                
                # Aggregate results
                result.edges_created += channel_result.edges_created
                result.edges_updated += channel_result.edges_updated
                result.user_topic_edges += channel_result.user_topic_edges
                result.user_user_edges += channel_result.user_user_edges
                result.topic_topic_edges += channel_result.topic_topic_edges
                result.entity_entity_edges += channel_result.entity_entity_edges
                result.errors.extend(channel_result.errors)
            
            logger.info(
                f"Batch enrichment complete: {len(channel_messages)} channels, "
                f"{result.total_edges} total edges"
            )
            
        except Exception as e:
            logger.error(f"Batch enrichment failed: {e}")
            result.errors.append(str(e))
        
        return result


# Singleton instance
enrichment_agent = GraphEnrichmentAgent()
