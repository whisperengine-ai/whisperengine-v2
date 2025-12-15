from typing import List, Optional, Dict, Any
import yaml
from pathlib import Path
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from datetime import datetime
import time
from influxdb_client import Point

from src_v2.config.settings import settings
from src_v2.core.database import db_manager, retry_db_operation, require_db
from src_v2.core.cache import cache_manager
from src_v2.knowledge.extractor import FactExtractor, Fact
from src_v2.agents.llm_factory import create_llm
from src_v2.universe.privacy import privacy_manager

class KnowledgeManager:
    def __init__(self):
        self.extractor = FactExtractor()
        # Use reflective LLM for Cypher generation (utility task, not character response)
        # CRITICAL: max_tokens=512 prevents runaway generation loops in local models (Qwen, etc.)
        # Cypher queries should never exceed ~300 tokens; 512 gives headroom for edge cases
        self.llm = create_llm(temperature=0.0, mode="reflective", max_tokens=512, request_timeout=30)
        
        self.cypher_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert Neo4j Cypher developer.
Your task is to convert a natural language question into a Cypher query to retrieve information about a user OR the AI character.

CRITICAL: You MUST output ONLY a valid Cypher query or RETURN "NO_ANSWER". Never output explanations, conversations, or prose.

SCHEMA:
- Nodes: 
    - (:User {{id: $user_id}})
    - (:Character {{name: $bot_name}})
    - (:Entity {{name: "..."}})
- Relationships: [:FACT {{predicate: "..."}}] 
    - Common Predicates: "LIKES", "LOVES", "DISLIKES", "OWNS", "LIVES_IN", "HAS_JOB", "HAS_GOAL", "IS_A"

EXAMPLES:
1. Q: "What do I like?" / "What are my hobbies?"
   A: MATCH (u:User {{id: $user_id}})-[r:FACT]->(o:Entity) WHERE r.predicate IN ['LIKES', 'LOVES', 'INTERESTED_IN', 'ENJOYS'] RETURN o.name, r.predicate

2. Q: "Where do I live?"
   A: MATCH (u:User {{id: $user_id}})-[r:FACT]->(o:Entity) WHERE r.predicate = 'LIVES_IN' RETURN o.name

3. Q: "Where did you grow up?" (asking the bot)
   A: MATCH (c:Character {{name: $bot_name}})-[r:FACT]->(o:Entity) WHERE r.predicate = 'GREW_UP_IN' OR r.predicate = 'ORIGIN' RETURN o.name

4. Q: "Do we have anything in common?"
   A: MATCH (u:User {{id: $user_id}})-[r1:FACT]->(e:Entity)<-[r2:FACT]-(c:Character {{name: $bot_name}}) RETURN e.name, r1.predicate

5. Q: "pinky finger callus" (keyword search)
   A: MATCH (n)-[r:FACT]->(o:Entity) WHERE ((n:User AND n.id = $user_id) OR (n:Character AND n.name = $bot_name)) AND (o.name CONTAINS 'pinky' OR o.name CONTAINS 'callus') RETURN labels(n)[0] as owner, o.name, r.predicate

6. Q: "Who is user with id 12345?"
   A: MATCH (u:User {{id: '12345'}})-[r:FACT]->(o:Entity) RETURN o.name, r.predicate

RULES:
- Use the parameter $user_id for the User node by default.
- If the question specifies a specific User ID (e.g. "user with id 123"), use that ID string directly in the query (e.g. {{id: '123'}}).
- ALWAYS use the parameter $bot_name for the Character node.
- If the query is ambiguous about the target (User vs Character), search BOTH.
- Return the relevant properties (usually o.name or r.predicate).
- Do NOT include markdown formatting (```cypher). Just the raw query.
- Use case-insensitive matching if unsure (e.g., toLower(r.predicate) = 'likes').
- For "hobbies" or "interests", ALWAYS check for 'LIKES', 'LOVES', 'ENJOYS'.
- If the question is about general knowledge (songs, movies, history, celebrities, facts about the world), return exactly: RETURN "NO_ANSWER"
- If the question cannot be answered by the schema (e.g. asking for chat history, weather, time), return exactly: RETURN "NO_ANSWER"
- Do NOT use UNION queries. Instead, use a single MATCH with OR conditions or multiple patterns separated by commas.
- Ensure the query contains exactly ONE 'RETURN' clause, and it must be at the very end.
- Do not chain multiple queries with semicolons.
- NEVER respond with a conversational message. Only output Cypher or RETURN "NO_ANSWER".
- NEVER use CREATE or MERGE - this is a READ-ONLY query function. Only use MATCH/OPTIONAL MATCH/RETURN.
- Do not include any explanation or text before or after the query.
- Do not use markdown code blocks.
- CRITICAL: In WHERE clauses, do NOT use pattern syntax like (n:User {id: ...}). Use (n:User AND n.id = ...) instead.
- CRITICAL: When using OR conditions in WHERE clauses, ensure proper parentheses grouping.

{privacy_instructions}
"""),
            ("human", "{question}")
        ])
        self.cypher_chain = self.cypher_prompt | self.llm | StrOutputParser()

        # New: Fact Correction Chain
        self.correction_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert Neo4j Cypher developer.
Your task is to generate a Cypher query to DELETE or UPDATE a fact based on a user's correction.

SCHEMA:
- Nodes: (:User {{id: $user_id}}), (:Entity {{name: "..."}})
- Relationships: [:FACT {{predicate: "..."}}]

EXAMPLES:
1. User: "I don't like pizza anymore."
   Query: MATCH (u:User {{id: $user_id}})-[r:FACT]->(o:Entity {{name: 'Pizza'}}) WHERE r.predicate = 'LIKES' DELETE r

2. User: "Actually, I live in Seattle now, not Portland."
   Query: MATCH (u:User {{id: $user_id}})-[r:FACT {{predicate: 'LIVES_IN'}}]->(o:Entity) DELETE r WITH u MERGE (new_loc:Entity {{name: 'Seattle'}}) MERGE (u)-[:FACT {{predicate: 'LIVES_IN', confidence: 1.0}}]->(new_loc)

3. User: "Forget that I own a cat."
   Query: MATCH (u:User {{id: $user_id}})-[r:FACT]->(o:Entity) WHERE r.predicate = 'OWNS' AND o.name CONTAINS 'cat' DELETE r

RULES:
- Use $user_id parameter.
- Return ONLY the raw Cypher query. No markdown.
- Be careful with DELETE operations.
- CRITICAL: When using MERGE after DELETE, you MUST use WITH to carry forward variables.
- Always keep DELETE...WITH...MERGE patterns on a single logical flow.
"""),
            ("human", "{correction}")
        ])
        self.correction_chain = self.correction_prompt | self.llm | StrOutputParser()

    @require_db("neo4j")
    async def initialize(self):
        """
        Initializes the Knowledge Graph schema (constraints and indexes).
        """
        try:
            async with db_manager.neo4j_driver.session() as session:
                # Create constraints (which also create indexes)
                # User id must be unique
                await session.run("CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
                
                # Entity name should be indexed/unique
                await session.run("CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE")
                
                # Phase 2.5.1: Memory node constraint for Graph Unification
                # Memory id (vector_id from Qdrant) must be unique
                await session.run("CREATE CONSTRAINT memory_id_unique IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE")
                
                # Register relationship types and properties to avoid warnings
                # Create a dummy pattern and delete it immediately
                await session.run("""
                    MERGE (u:User {id: '_schema_init_'})
                    MERGE (e:Entity {name: '_schema_init_'})
                    MERGE (u)-[r:FACT {predicate: '_init_', confidence: 0.0}]->(e)
                    DELETE r, u, e
                """)

                logger.info("Knowledge Graph schema initialized.")
            
            # Auto-ingest character background if available
            if settings.DISCORD_BOT_NAME:
                await self.ingest_character_background(settings.DISCORD_BOT_NAME)

        except Exception as e:
            logger.error(f"Failed to initialize Knowledge Graph schema: {e}")

    @require_db("neo4j")
    @retry_db_operation(max_retries=3)
    async def ingest_character_background(self, bot_name: str):
        """
        Ingests character background facts from characters/<bot_name>/background.yaml
        """
        yaml_path = Path(f"characters/{bot_name}/background.yaml")
        if not yaml_path.exists():
            logger.debug(f"No background.yaml found for {bot_name}. Skipping ingestion.")
            return

        try:
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)
            
            facts = data.get("facts", [])
            if not facts:
                return

            logger.info(f"Ingesting {len(facts)} background facts for {bot_name}...")
            
            async with db_manager.neo4j_driver.session() as session:
                # Ensure Character Node exists
                await session.run("MERGE (c:Character {name: $name})", name=bot_name)
                
                for fact in facts:
                    predicate = fact["predicate"]
                    obj = fact["object"]
                    
                    # Create Entity and Relationship (Idempotent MERGE)
                    query = """
                    MATCH (c:Character {name: $name})
                    MERGE (e:Entity {name: $obj})
                    MERGE (c)-[r:FACT {predicate: $predicate}]->(e)
                    ON CREATE SET r.mention_count = 1, r.confidence = 1.0, r.created_at = datetime()
                    ON MATCH SET r.mention_count = coalesce(r.mention_count, 1)
                    """
                    await session.run(query, name=bot_name, obj=obj, predicate=predicate)
            
            logger.info(f"Successfully ingested background for {bot_name}.")

        except Exception as e:
            logger.error(f"Failed to ingest background for {bot_name}: {e}")

    @require_db("neo4j", default_return="Graph database not available.")
    async def query_graph(self, user_id: str, question: str, bot_name: str = "default") -> str:
        """
        Generates and executes a Cypher query based on a natural language question.
        """
        try:
            # 1. Check Privacy Settings
            privacy_settings = await privacy_manager.get_settings(user_id)
            privacy_instructions = ""
            
            if not privacy_settings.get("share_with_other_bots", True):
                # Restrict to facts learned by this bot OR facts with no source (legacy)
                privacy_instructions = """
PRIVACY RESTRICTION ENABLED:
- The user has disabled sharing data between bots.
- You MUST append a WHERE clause to filter relationships.
- ONLY match relationships where `r.source_bot = $bot_name` OR `r.source_bot` IS NULL.
- Example: MATCH ... WHERE ... AND (r.source_bot = $bot_name OR r.source_bot IS NULL) ...
"""

            # 2. Generate Cypher
            cypher_query = await self.cypher_chain.ainvoke({
                "question": question,
                "privacy_instructions": privacy_instructions
            })
            cypher_query = cypher_query.replace("```cypher", "").replace("```", "").strip()
            
            # Handle "NO_ANSWER" case
            if 'RETURN "NO_ANSWER"' in cypher_query or "NO_ANSWER" in cypher_query:
                return "No relevant information found in the graph (out of scope)."

            # === RUNAWAY GENERATION DETECTION ===
            # Local models (Qwen, Llama, etc.) can enter repetition loops, generating
            # massive queries with repeated UNION clauses. Detect and reject these.
            
            # 1. Length check: Valid Cypher queries rarely exceed 1500 chars
            if len(cypher_query) > 1500:
                logger.warning(f"Rejecting oversized Cypher query ({len(cypher_query)} chars). Likely runaway generation.")
                return "No relevant information found in the graph (query too complex)."
            
            # 2. UNION repetition check: More than 3 UNIONs suggests runaway pattern
            union_count = cypher_query.upper().count("UNION")
            if union_count > 3:
                logger.warning(f"Rejecting Cypher with {union_count} UNIONs. Likely runaway generation loop.")
                return "No relevant information found in the graph (query too complex)."
            
            # 3. Repetition pattern detection: Same substring repeated multiple times
            # Check if any 50+ char substring appears more than twice (indicates loop)
            if len(cypher_query) > 200:
                chunk_size = 50
                seen_chunks = {}
                for i in range(0, len(cypher_query) - chunk_size, 20):  # Sliding window
                    chunk = cypher_query[i:i+chunk_size]
                    seen_chunks[chunk] = seen_chunks.get(chunk, 0) + 1
                    if seen_chunks[chunk] > 2:
                        logger.warning(f"Rejecting Cypher with repeated patterns ({len(cypher_query)} chars). Likely runaway generation.")
                        return "No relevant information found in the graph (query too complex)."

            # Basic validation: Ensure it starts with a valid Cypher keyword
            valid_starts = ["MATCH", "CALL", "RETURN", "WITH", "OPTIONAL MATCH"]
            cypher_upper = cypher_query.upper()
            if not any(cypher_upper.startswith(keyword) for keyword in valid_starts):
                # Detect conversational responses (LLM hallucinating instead of returning Cypher)
                # These typically contain sentence-ending punctuation or are too long for a query
                if len(cypher_query) > 200 or any(marker in cypher_query for marker in ['. ', '? ', '! ', 'I understand', 'Would you like']):
                    logger.debug(f"LLM returned conversational response instead of Cypher (question: {question[:50]}...)")
                else:
                    logger.warning(f"LLM generated invalid Cypher: {cypher_query[:200]}")
                return "No relevant information found in the graph (out of scope)."
            
            # SAFETY: Reject write operations in read-only query_graph
            write_keywords = ["CREATE", "MERGE", "DELETE", "SET ", "REMOVE"]
            if any(keyword in cypher_upper for keyword in write_keywords):
                logger.warning(f"LLM generated write query in read-only context, rejecting: {cypher_query[:100]}")
                return "No relevant information found in the graph (out of scope)."

            logger.info(f"Generated Cypher: {cypher_query}")

            # 2. Execute
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run(cypher_query, user_id=user_id, bot_name=bot_name)
                records = await result.data()
                
                if not records:
                    return "No relevant information found in the graph."
                
                # Format results
                formatted_results = []
                for record in records:
                    # Flatten the record values
                    # Sanitize braces to prevent LangChain prompt formatting errors
                    values = [str(v).replace("{", "(").replace("}", ")") for v in record.values()]
                    formatted_results.append(" ".join(values))
                
                return ", ".join(formatted_results)

        except Exception as e:
            logger.error(f"Graph query failed: {e}")
            return "Error querying knowledge graph."

    async def delete_fact(self, user_id: str, correction: str) -> str:
        """
        Generates and executes a Cypher query to delete/update facts based on user input.
        """
        if not db_manager.neo4j_driver:
            return "Graph database not available."

        try:
            # 1. Generate Cypher
            cypher_query = await self.correction_chain.ainvoke({"correction": correction})
            cypher_query = cypher_query.replace("```cypher", "").replace("```", "").strip()
            
            logger.info(f"Generated Correction Cypher: {cypher_query}")

            # 2. Execute
            async with db_manager.neo4j_driver.session() as session:
                # We use execute_write for modifications
                await session.run(cypher_query, user_id=user_id)
                
                # Invalidate common ground cache
                await cache_manager.delete_pattern(f"knowledge:common_ground:*:{user_id}")
                
                return "Fact updated successfully."

        except Exception as e:
            logger.error(f"Fact correction failed: {e}")
            return "Failed to update fact."

    async def add_memory_node(
        self, 
        user_id: str, 
        vector_id: str, 
        content: str, 
        timestamp: str, 
        source_type: str, 
        bot_name: Optional[str] = None,
        # ADR-014: Author tracking fields
        author_id: Optional[str] = None,
        author_is_bot: bool = False
    ):
        """
        Creates a (:Memory) node in the graph linked to the user.
        This enables 'Vector-First Traversal' (Phase 2.5.1).
        
        ADR-014: Now includes author_id and author_is_bot to properly
        attribute memories in multi-party conversations.
        
        IMPORTANT: Memory nodes get a human-readable `name` property (truncated
        content) to prevent UUID leakage in graph walks. Without this, GraphWalker
        would expose raw Qdrant point UUIDs in dream/diary interpretations.
        """
        if not db_manager.neo4j_driver:
            return

        # Create human-readable name from content to prevent UUID leak in graph walks
        # Use first 50 chars of content or a fallback label
        memory_name = content[:50].strip() if content else "memory"
        if len(content) > 50:
            memory_name += "..."
        
        query = """
        MERGE (u:User {id: $user_id})
        ON CREATE SET u.is_bot = false
        CREATE (m:Memory {
            id: $vector_id,
            name: $name,
            content: $content,
            timestamp: $timestamp,
            source_type: $source_type,
            bot_name: $bot_name,
            author_id: $author_id,
            author_is_bot: $author_is_bot
        })
        MERGE (u)-[:HAS_MEMORY]->(m)
        
        // ADR-014: If author is different from user (bot response), link to author too
        WITH m
        WHERE $author_id IS NOT NULL AND $author_id <> $user_id
        MERGE (a:User {id: $author_id})
        ON CREATE SET a.is_bot = $author_is_bot
        MERGE (a)-[:AUTHORED]->(m)
        """
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                await session.run(
                    query, 
                    user_id=user_id, 
                    vector_id=vector_id,
                    name=memory_name,
                    content=content, 
                    timestamp=timestamp, 
                    source_type=source_type,
                    bot_name=bot_name,
                    author_id=author_id,
                    author_is_bot=author_is_bot
                )
                logger.debug(f"Created graph memory node {vector_id}")
        except Exception as e:
            logger.error(f"Failed to create memory node: {e}")

    async def get_memory_neighborhood(self, vector_ids: List[str], max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        Given vector IDs from Qdrant search, retrieves the graph neighborhood.
        This is the 'Vector-First Search' part of Phase 2.5.1.
        
        Returns facts and entities connected to the memories.
        """
        if not db_manager.neo4j_driver or not vector_ids:
            return []
        
        # Query: Starting from Memory nodes, find connected User, then their Facts
        # Also find connected Memories (Structural Consolidation)
        query = """
        MATCH (m:Memory)
        WHERE m.id IN $vector_ids
        
        // 1. User Context (Existing)
        OPTIONAL MATCH (m)<-[:HAS_MEMORY]-(u:User)-[r:FACT]->(e:Entity)
        
        // 2. Memory Connections (New - Reverie/Dream Links)
        OPTIONAL MATCH (m)-[r2]-(m2:Memory)
        WHERE type(r2) IN ['DREAM_ASSOCIATION', 'REVERIE_LINK', 'THEMATIC_LINK']
        
        RETURN DISTINCT 
            m.id as memory_id,
            u.id as user_id,
            e.name as entity,
            r.predicate as predicate,
            r.confidence as confidence,
            m2.content as linked_memory_content,
            type(r2) as link_type
        LIMIT 20
        """
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run(query, vector_ids=vector_ids)
                records = await result.data()
                
                # Group by memory_id for easier consumption
                neighborhood = []
                for record in records:
                    # Add User Facts
                    if record.get("entity"):
                        neighborhood.append({
                            "memory_id": record["memory_id"],
                            "user_id": record["user_id"],
                            "entity": record["entity"],
                            "predicate": record["predicate"],
                            "confidence": record.get("confidence", 1.0)
                        })
                    
                    # Add Linked Memories
                    if record.get("linked_memory_content"):
                        # Truncate content for display
                        content = record["linked_memory_content"] or ""
                        if len(content) > 50:
                            content = content[:47] + "..."
                            
                        neighborhood.append({
                            "memory_id": record["memory_id"],
                            "entity": f"Memory: {content}",
                            "predicate": record["link_type"],
                            "confidence": 1.0
                        })
                
                return neighborhood
        except Exception as e:
            logger.error(f"Failed to get memory neighborhood: {e}")
            return []

    async def find_common_ground(self, user_id: str, bot_name: str) -> str:
        """
        Finds shared facts or entities between the user and the bot.
        Searches for:
        1. Direct connections (User -> Entity <- Bot)
        2. Shared categories (User -> Entity -> Category <- Entity <- Bot)
        """
        cache_key = f"knowledge:common_ground:{bot_name}:{user_id}"
        cached_data = await cache_manager.get(cache_key)
        if cached_data is not None:
            return cached_data

        if not db_manager.neo4j_driver:
            return ""

        # 1. Direct Connections
        query_direct = """
        MATCH (u:User {id: $user_id})-[r1:FACT]->(e:Entity)<-[r2:FACT]-(c:Character {name: $bot_name})
        RETURN e.name, r1.predicate, r2.predicate, "direct" as type
        LIMIT 3
        """
        
        # 2. Shared Categories/Concepts (2-hop)
        # e.g. User likes "Star Wars" (Sci-Fi) and Bot likes "Dune" (Sci-Fi)
        # Assuming we have some category structure or shared properties
        query_category = """
        MATCH (u:User {id: $user_id})-[r1:FACT]->(e1:Entity)-[:IS_A|BELONGS_TO]->(cat:Entity)<-[:IS_A|BELONGS_TO]-(e2:Entity)<-[r2:FACT]-(c:Character {name: $bot_name})
        WHERE e1 <> e2
        RETURN cat.name as category, e1.name as user_item, e2.name as bot_item, "category" as type
        LIMIT 2
        """
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                # Run Direct Check
                result_direct = await session.run(query_direct, user_id=user_id, bot_name=bot_name)
                records_direct = await result_direct.data()
                
                connections = []
                for r in records_direct:
                    connections.append(f"- You both connect to '{r['e.name']}' (User: {r['r1.predicate']}, You: {r['r2.predicate']})")
                
                # Run Category Check (if we have room)
                if len(connections) < 3:
                    result_cat = await session.run(query_category, user_id=user_id, bot_name=bot_name)
                    records_cat = await result_cat.data()
                    for r in records_cat:
                        connections.append(f"- You both like {r['category']} (User: {r['user_item']}, You: {r['bot_item']})")

                # 3. Match Traits to Facts (Cross-System: Universe <-> Knowledge)
                # Matches User Traits (from Universe) with Bot Facts (from Knowledge Graph)
                if len(connections) < 5:
                    query_trait_fact = """
                    MATCH (u:User {id: $user_id})-[r1:HAS_TRAIT]->(t:Trait)
                    MATCH (c:Character {name: $bot_name})-[r2:FACT]->(e:Entity)
                    WHERE toLower(t.name) = toLower(e.name)
                    RETURN t.name as shared, "trait_fact" as type
                    LIMIT 3
                    """
                    result_trait = await session.run(query_trait_fact, user_id=user_id, bot_name=bot_name)
                    records_trait = await result_trait.data()
                    for r in records_trait:
                        connections.append(f"- Shared Interest: {r['shared']} (You know this from your background, User has this trait)")

                result_str = "\n".join(connections) if connections else ""
                await cache_manager.set(cache_key, result_str)
                return result_str
        except Exception as e:
            logger.error(f"Common ground check failed: {e}")
            return ""

    ALLOWED_MEMORY_RELATIONSHIPS = frozenset({"DREAM_ASSOCIATION", "REVERIE_LINK", "THEMATIC_LINK", "TEMPORAL_SEQUENCE", "EMOTIONAL_RESONANCE"})

    async def link_memories(self, source_id: str, target_id: str, relationship_type: str = "DREAM_ASSOCIATION", weight: float = 1.0):
        """
        Creates a relationship between two memory nodes in the graph.
        Used for Structural Consolidation during dreaming.
        """
        if not db_manager.neo4j_driver:
            return

        # Validate relationship type to prevent Cypher injection
        if relationship_type not in self.ALLOWED_MEMORY_RELATIONSHIPS:
            logger.warning(f"Invalid relationship type '{relationship_type}', using DREAM_ASSOCIATION")
            relationship_type = "DREAM_ASSOCIATION"

        query = f"""
        MATCH (m1:Memory {{id: $source_id}})
        MATCH (m2:Memory {{id: $target_id}})
        MERGE (m1)-[r:{relationship_type}]->(m2)
        ON CREATE SET r.weight = $weight, r.created_at = datetime()
        ON MATCH SET r.weight = coalesce(r.weight, 0) + $weight, r.updated_at = datetime()
        """
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                await session.run(query, source_id=source_id, target_id=target_id, weight=weight)
                logger.debug(f"Linked memories {source_id} -> {target_id} ({relationship_type})")
        except Exception as e:
            logger.error(f"Failed to link memories: {e}")

    @require_db("neo4j", default_return="")
    async def search_bot_background(self, bot_name: str, user_message: str) -> str:
        """
        Checks if the user's message mentions anything related to the bot's background.
        """
        # Simple keyword extraction (split by space, filter small words)
        keywords = [w for w in user_message.lower().split() if len(w) > 4]
        if not keywords:
            return ""

        # Construct a dynamic OR query for keywords
        # This is a basic implementation. A full-text index would be better for production.
        where_clause = " OR ".join([f"toLower(e.name) CONTAINS '{k}'" for k in keywords])
        
        query = f"""
        MATCH (c:Character {{name: $bot_name}})-[r:FACT]->(e:Entity)
        WHERE {where_clause}
        RETURN r.predicate, e.name
        LIMIT 3
        """
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run(query, bot_name=bot_name)
                records = await result.data()
                
                if not records:
                    return ""
                
                hits = []
                for r in records:
                    hits.append(f"- Relevant to your background: {r['r.predicate']} {r['e.name']}")
                
                return "\n".join(hits)
        except Exception as e:
            # Syntax error in query construction or connection issue
            # logger.error(f"Background search failed: {e}") 
            return ""

    @retry_db_operation(max_retries=3)
    @require_db("neo4j")
    async def process_user_message(self, user_id: str, message: str, bot_name: str = "unknown"):
        """
        Extracts facts from the message and stores them in the Knowledge Graph.
        """
        if not settings.ENABLE_RUNTIME_FACT_EXTRACTION:
            return

        # 1. Extract Facts
        facts = await self.extractor.extract_facts(message)
        if not facts:
            return

        await self.save_facts(user_id, facts, bot_name)

    async def _get_known_bot_names(self) -> set:
        """
        Get known bot names from Redis cache or filesystem.
        Used to prevent storing bot names as entities in the Knowledge Graph.
        """
        cache_key = "system:known_bot_names"
        
        # 1. Try Redis
        cached_names = await cache_manager.get_json(cache_key)
        if cached_names:
            return set(cached_names)
            
        # 2. Fallback to Filesystem
        bot_names = {
            "sage", "becky", "silas", "liln"  # External/Aliases
        }
        try:
            char_dir = Path("characters")
            if char_dir.exists():
                for p in char_dir.iterdir():
                    if p.is_dir() and (p / "character.md").exists():
                        bot_names.add(p.name.lower())
            
            # Cache for 1 hour
            await cache_manager.set_json(cache_key, list(bot_names), ttl=3600)
            
        except Exception as e:
            logger.warning(f"Failed to load dynamic bot names: {e}")
            
        return bot_names

    @retry_db_operation(max_retries=3)
    @require_db("neo4j")
    async def save_facts(self, user_id: str, facts: List[Fact], bot_name: str = "unknown", is_self_reflection: bool = False):
        """
        Saves a list of facts to Neo4j.
        Includes validation to filter out common LLM hallucinations.
        
        Args:
            is_self_reflection: If True, facts are attributed to the Character node, not a User node.
        """
        if not facts:
            return
        
        # === FACT VALIDATION ===
        # Filter out common LLM hallucinations before saving to Neo4j
        valid_facts = []
        
        # Get known bot names (cached)
        BOT_NAMES = await self._get_known_bot_names()
        
        # Meta-categories that are useless as facts
        INVALID_OBJECTS = {
            "user", "ai", "bot", "human", "person", "entity", 
            "assistant", "chatbot", "pet",  # Generic, not specific
            "career", "family", "husband", "wife", "friend", "companion",
            "system", "presence", "song", "conversation", "memory",
            "something", "anything", "nothing", "everything"  # Vague
        }
        
        # Invalid predicates that produce low-value facts
        INVALID_PREDICATES = {
            "HAS_A", "EXIST_IN", "NOTICED", "SAID", "ASKED", "TOLD",
            "MENTIONED", "TALKED_ABOUT", "DISCUSSED"  # Conversational, not factual
        }
        
        # Try to get user's display name to avoid storing it as an entity
        # (e.g., username "markanthony" being stored as a pet name)
        user_names_to_block = set()
        try:
            from src_v2.core.database import db_manager
            if db_manager.postgres_pool:
                async with db_manager.postgres_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT user_name FROM v2_chat_history WHERE user_id = $1 AND user_name IS NOT NULL ORDER BY timestamp DESC LIMIT 1",
                        user_id
                    )
                    if row and row['user_name']:
                        # Add variations of the username
                        name = row['user_name'].lower().strip()
                        user_names_to_block.add(name)
                        # Also block without spaces/underscores
                        user_names_to_block.add(name.replace(" ", ""))
                        user_names_to_block.add(name.replace("_", ""))
        except Exception:
            pass  # Fail silently, validation continues
        
        # Animals that users can't "be"
        ANIMAL_TYPES = {"cat", "dog", "bird", "fish", "hamster", "rabbit", "snake", "turtle"}
        
        for fact in facts:
            obj_lower = fact.object.lower().strip()
            subj_lower = fact.subject.lower().strip()
            predicate = fact.predicate.upper()
            
            # 1. Reject facts with JSON artifacts (malformed parsing)
            if any(char in fact.object for char in ['{', '}', '[', ']']):
                logger.debug(f"Rejecting malformed fact: {fact.predicate} -> {fact.object}")
                continue
            
            # 2. Reject facts where object is a bot name
            if obj_lower in BOT_NAMES:
                logger.debug(f"Rejecting bot-name fact: {fact.predicate} -> {fact.object}")
                continue
            
            # 3. Reject facts where object is the user's own name (username confusion)
            if obj_lower in user_names_to_block:
                logger.debug(f"Rejecting user-name-as-entity fact: {fact.predicate} -> {fact.object}")
                continue
            
            # 4. Reject useless meta-categories
            if obj_lower in INVALID_OBJECTS:
                logger.debug(f"Rejecting meta-category fact: {fact.predicate} -> {fact.object}")
                continue
            
            # 5. Reject invalid predicates (conversational, not factual)
            if predicate in INVALID_PREDICATES:
                logger.debug(f"Rejecting invalid predicate: {predicate} -> {fact.object}")
                continue
            
            # 6. Reject "User IS_A <animal>" hallucinations
            if subj_lower == "user" and predicate == "IS_A" and obj_lower in ANIMAL_TYPES:
                logger.debug(f"Rejecting User IS_A animal: {fact.object}")
                continue
            
            # 7. Reject self-referential facts
            if subj_lower == obj_lower:
                logger.debug(f"Rejecting self-referential fact: {fact.subject} -> {fact.object}")
                continue
            
            # 8. Reject very short or very long objects (likely noise)
            if len(fact.object.strip()) < 2 or len(fact.object.strip()) > 100:
                logger.debug(f"Rejecting invalid length object: {fact.object}")
                continue
            
            valid_facts.append(fact)
        
        if not valid_facts:
            logger.debug(f"All {len(facts)} facts filtered out for user {user_id}")
            return
        
        logger.info(f"Saving {len(valid_facts)}/{len(facts)} facts for user {user_id} (source: {bot_name}, self_reflection={is_self_reflection})")

        # 2. Store in Neo4j
        async with db_manager.neo4j_driver.session() as session:
            for fact in valid_facts:
                await session.execute_write(self._merge_fact, user_id, fact, bot_name, is_self_reflection)
        
        # Invalidate common ground cache for this user (across all bots)
        await cache_manager.delete_pattern(f"knowledge:common_ground:*:{user_id}")

    @staticmethod
    async def _merge_fact(tx, user_id: str, fact: Fact, bot_name: str, is_self_reflection: bool = False):
        """
        Cypher query to merge the fact into the graph.
        Handles single-value predicates and antonym conflicts.
        """
        SINGLE_VALUE_PREDICATES = {"LIVES_IN", "HAS_NAME", "IS_AGED", "HAS_GENDER"}
        ANTONYM_PAIRS = {
            "LIKES": ["HATES", "DISLIKES"],
            "LOVES": ["HATES", "DISLIKES"],
            "HATES": ["LIKES", "LOVES"],
            "DISLIKES": ["LIKES", "LOVES"]
        }
        
        predicate = fact.predicate.upper()

        # Determine Subject Node (User or Character)
        if is_self_reflection:
            # If self-reflection, the subject is the Character
            subject_match = "MATCH (s:Character {name: $bot_name})"
            subject_merge = "MERGE (s:Character {name: $bot_name})"
            # We don't delete old facts for characters as aggressively to preserve history/personality
            # But we still handle single-value updates
        else:
            # Normal case: Subject is the User
            subject_match = "MATCH (s:User {id: $user_id})"
            subject_merge = "MERGE (s:User {id: $user_id})"

        # 1. Handle Single Value Predicates (Global overwrite)
        if predicate in SINGLE_VALUE_PREDICATES:
            delete_query = f"""
            {subject_match}
            MATCH (s)-[r:FACT {{predicate: $predicate}}]->()
            DELETE r
            """
            await tx.run(delete_query, user_id=user_id, bot_name=bot_name, predicate=predicate)

        # 2. Handle Antonyms (Specific object overwrite)
        if predicate in ANTONYM_PAIRS:
            antonyms = ANTONYM_PAIRS[predicate]
            delete_antonym_query = f"""
            {subject_match}
            MATCH (s)-[r:FACT]->(o:Entity {{name: $object_name}})
            WHERE r.predicate IN $antonyms
            DELETE r
            """
            await tx.run(delete_antonym_query, 
                         user_id=user_id, 
                         bot_name=bot_name,
                         object_name=fact.object, 
                         antonyms=antonyms)

        # 3. Merge New Fact
        query_safe = f"""
        {subject_merge}
        MERGE (o:Entity {{name: $object_name}})
        MERGE (s)-[r:FACT {{predicate: $predicate}}]->(o)
        ON CREATE SET 
            r.confidence = $confidence, 
            r.source_bot = $bot_name, 
            r.created_at = datetime(), 
            r.updated_at = datetime(),
            r.mention_count = 1
        ON MATCH SET 
            r.updated_at = datetime(),
            r.mention_count = coalesce(r.mention_count, 1) + 1,
            r.confidence = CASE WHEN $confidence > r.confidence THEN $confidence ELSE r.confidence END
        """
        
        await tx.run(query_safe, 
                     user_id=user_id, 
                     bot_name=bot_name,
                     object_name=fact.object, 
                     predicate=predicate,
                     confidence=fact.confidence)

    @require_db("neo4j", default_return=[])
    async def get_recent_observations_by(self, bot_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent observations (facts) extracted by a specific bot.
        Used for dreams and diaries to reflect on what the bot has learned recently.
        """
        query = """
        MATCH (u:User)-[r:FACT]->(o:Entity)
        WHERE r.source_bot = $bot_name
        RETURN u.id as user_id, r.predicate as predicate, o.name as object, toString(r.created_at) as created_at
        ORDER BY r.created_at DESC
        LIMIT $limit
        """
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run(query, bot_name=bot_name, limit=limit)
                records = await result.data()
                return records
        except Exception as e:
            logger.error(f"Failed to get recent observations by {bot_name}: {e}")
            return []

    @require_db("neo4j", default_return="")
    async def get_user_knowledge(self, user_id: str, query: Optional[str] = None, limit: int = 10) -> str:
        """
        Retrieves relevant facts about the user from the Knowledge Graph.
        If query is provided, it generates a specific Cypher query.
        Otherwise, it returns general facts.
        """
        start_time = time.time()

        try:
            async with db_manager.neo4j_driver.session() as session:
                if query:
                    # 1. Generate Cypher from Natural Language
                    cypher_query = await self.cypher_chain.ainvoke({"question": query})
                    # Clean up markdown if present
                    cypher_query = cypher_query.replace("```cypher", "").replace("```", "").strip()
                    
                    if "NO_ANSWER" in cypher_query:
                        return ""
                        
                    logger.debug(f"Generated Cypher: {cypher_query}")
                    
                    # 2. Execute Query
                    result = await session.run(cypher_query, user_id=user_id, bot_name=settings.DISCORD_BOT_NAME)
                    records = await result.data()
                    
                    # Log metrics
                    if db_manager.influxdb_write_api:
                        try:
                            duration_ms = (time.time() - start_time) * 1000
                            point = Point("knowledge_latency") \
                                .tag("user_id", user_id) \
                                .tag("type", "query") \
                                .field("duration_ms", duration_ms) \
                                .field("result_count", len(records)) \
                                .time(datetime.utcnow())
                            
                            db_manager.influxdb_write_api.write(
                                bucket=settings.INFLUXDB_BUCKET,
                                org=settings.INFLUXDB_ORG,
                                record=point
                            )
                        except Exception as e:
                            logger.error(f"Failed to log knowledge metrics: {e}")

                    if not records:
                        return ""
                    
                    # Format results
                    formatted_results = []
                    for record in records:
                        values = [str(v) for v in record.values()]
                        formatted_results.append(" ".join(values))
                    
                    return "\n".join(formatted_results)
                
                else:
                    # Default: Get all facts about the user
                    # Limit to requested number (default 10)
                    result = await session.run("""
                        MATCH (u:User {id: $user_id})-[r:FACT]->(e:Entity)
                        RETURN r.predicate, e.name
                        ORDER BY r.created_at DESC
                        LIMIT $limit
                    """, user_id=user_id, limit=limit)
                    
                    records = await result.data()
                    
                    # Log metrics
                    if db_manager.influxdb_write_api:
                        try:
                            duration_ms = (time.time() - start_time) * 1000
                            point = Point("knowledge_latency") \
                                .tag("user_id", user_id) \
                                .tag("type", "default") \
                                .field("duration_ms", duration_ms) \
                                .field("result_count", len(records)) \
                                .time(datetime.utcnow())
                            
                            db_manager.influxdb_write_api.write(
                                bucket=settings.INFLUXDB_BUCKET,
                                org=settings.INFLUXDB_ORG,
                                record=point
                            )
                        except Exception as e:
                            logger.error(f"Failed to log knowledge metrics: {e}")

                    if not records:
                        return ""
                        
                    facts = []
                    for r in records:
                        facts.append(f"- User {r['r.predicate']} {r['e.name']}")
                    
                    return "\n".join(facts)

        except Exception as e:
            logger.error(f"Failed to retrieve user knowledge: {e}")
            return ""

    @require_db("neo4j")
    async def clear_user_knowledge(self, user_id: str):
        """
        Deletes all facts associated with a user.
        """
        query = """
        MATCH (u:User {id: $user_id})-[r:FACT]->()
        DELETE r
        """
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                await session.run(query, user_id=user_id)
            logger.info(f"Cleared knowledge graph for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to clear user knowledge: {e}")

    @require_db("neo4j", default_return="Graph database not available.")
    async def explore_graph(
        self, 
        user_id: str, 
        bot_name: str, 
        start_node: str = "user", 
        depth: int = 2
    ) -> str:
        """
        Explores the knowledge graph from a starting point, returning connected entities.
        
        Args:
            user_id: The user's ID
            bot_name: The bot/character name
            start_node: "user", "character", or a specific entity name
            depth: How many hops to traverse (1-3)
        
        Returns:
            Formatted string of connected entities and relationships
        """
        depth = min(max(depth, 1), 3)  # Clamp between 1-3
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                results = []
                
                if start_node.lower() == "user":
                    # Explore from User node
                    if depth == 1:
                        query = """
                        MATCH (u:User {id: $user_id})-[r:FACT]->(e:Entity)
                        RETURN 'You' as source, r.predicate as relationship, e.name as target
                        LIMIT 15
                        UNION
                        MATCH (u:User {id: $user_id})-[:HAS_MEMORY]->(m:Memory)-[r2]-(m2:Memory)
                        WHERE type(r2) IN ['REVERIE_LINK', 'DREAM_ASSOCIATION', 'THEMATIC_LINK']
                        RETURN 'Your Memory' as source, type(r2) as relationship, 'Another Memory' as target
                        LIMIT 5
                        """
                    elif depth == 2:
                        query = """
                        MATCH path = (u:User {id: $user_id})-[r1:FACT]->(e1:Entity)
                        OPTIONAL MATCH (e1)-[r2:FACT|IS_A|BELONGS_TO]->(e2:Entity)
                        WHERE e2 IS NOT NULL
                        RETURN 'You' as source, r1.predicate as rel1, e1.name as mid, 
                               type(r2) as rel2, e2.name as target
                        LIMIT 20
                        UNION
                        MATCH (u:User {id: $user_id})-[r:FACT]->(e:Entity)
                        RETURN 'You' as source, r.predicate as rel1, e.name as mid, 
                               null as rel2, null as target
                        LIMIT 10
                        UNION
                        MATCH (u:User {id: $user_id})-[:HAS_MEMORY]->(m:Memory)-[r2]-(m2:Memory)
                        WHERE type(r2) IN ['REVERIE_LINK', 'DREAM_ASSOCIATION', 'THEMATIC_LINK']
                        RETURN 'Your Memory' as source, 'HAS_MEMORY' as rel1, m.content as mid,
                               type(r2) as rel2, m2.content as target
                        LIMIT 5
                        """
                    else:  # depth == 3
                        query = """
                        MATCH (u:User {id: $user_id})-[r1:FACT]->(e1:Entity)
                        OPTIONAL MATCH (e1)-[r2:FACT|IS_A|BELONGS_TO*1..2]->(e2:Entity)
                        WHERE e2 IS NOT NULL
                        RETURN 'You' as source, r1.predicate as rel1, e1.name as mid,
                               'connects to' as rel2, e2.name as target
                        LIMIT 25
                        UNION
                        MATCH (u:User {id: $user_id})-[:HAS_MEMORY]->(m:Memory)-[r2]-(m2:Memory)
                        WHERE type(r2) IN ['REVERIE_LINK', 'DREAM_ASSOCIATION', 'THEMATIC_LINK']
                        RETURN 'Your Memory' as source, 'HAS_MEMORY' as rel1, m.content as mid,
                               type(r2) as rel2, m2.content as target
                        LIMIT 5
                        """
                    
                    result = await session.run(query, user_id=user_id)
                    records = await result.data()
                    
                    if not records:
                        return "No connections found for this user in the knowledge graph."
                    
                    for r in records:
                        if r.get('target'):
                            results.append(f"• {r['source']} → {r['rel1']} → {r['mid']} → {r.get('rel2', '...')} → {r['target']}")
                        else:
                            results.append(f"• {r['source']} → {r['rel1']} → {r['mid']}")
                
                elif start_node.lower() == "character":
                    # Explore from Character node
                    query = """
                    MATCH (c:Character {name: $bot_name})-[r:FACT]->(e:Entity)
                    RETURN $bot_name as source, r.predicate as relationship, e.name as target
                    LIMIT 15
                    """
                    result = await session.run(query, bot_name=bot_name)
                    records = await result.data()
                    
                    if not records:
                        return f"No connections found for {bot_name} in the knowledge graph."
                    
                    for r in records:
                        results.append(f"• {r['source']} → {r['relationship']} → {r['target']}")
                    
                    # Also find common ground
                    common_query = """
                    MATCH (u:User {id: $user_id})-[r1:FACT]->(e:Entity)<-[r2:FACT]-(c:Character {name: $bot_name})
                    RETURN e.name as shared_entity, r1.predicate as user_rel, r2.predicate as char_rel
                    LIMIT 5
                    """
                    common_result = await session.run(common_query, user_id=user_id, bot_name=bot_name)
                    common_records = await common_result.data()
                    
                    if common_records:
                        results.append("\n🔗 Shared Connections (Common Ground):")
                        for r in common_records:
                            results.append(f"  • Both connected to '{r['shared_entity']}' (You: {r['user_rel']}, Me: {r['char_rel']})")
                
                else:
                    # Explore from a specific Entity
                    query = """
                    MATCH (e:Entity {name: $entity_name})<-[r:FACT]-(n)
                    RETURN labels(n)[0] as node_type, 
                           CASE WHEN n:User THEN 'User' ELSE n.name END as source,
                           r.predicate as relationship, 
                           e.name as target
                    LIMIT 10
                    UNION
                    MATCH (e:Entity {name: $entity_name})-[r:FACT|IS_A|BELONGS_TO]->(o:Entity)
                    RETURN 'Entity' as node_type, e.name as source, type(r) as relationship, o.name as target
                    LIMIT 10
                    """
                    result = await session.run(query, entity_name=start_node)
                    records = await result.data()
                    
                    if not records:
                        return f"No connections found for '{start_node}' in the knowledge graph."
                    
                    for r in records:
                        results.append(f"• {r['source']} → {r['relationship']} → {r['target']}")
                
                if not results:
                    return "No graph connections found."
                
                header = f"📊 Knowledge Graph Exploration (depth={depth}, from={start_node}):\n"
                return header + "\n".join(results)
                
        except Exception as e:
            logger.error(f"Graph exploration failed: {e}")
            return f"Error exploring graph: {e}"

    # ========== FACT HELPERS ==========

    @staticmethod
    async def _fetch_facts(tx, user_id: str, limit: int) -> List[str]:
        query = """
        MATCH (u:User {id: $user_id})-[r:FACT]->(o:Entity)
        RETURN r.predicate, o.name
        ORDER BY r.confidence DESC
        LIMIT $limit
        """
        result = await tx.run(query, user_id=user_id, limit=limit)
        records = await result.data()
        
        facts = []
        for record in records:
            predicate = record['r.predicate']
            obj = record['o.name']
            # Format: "User LIKES Pizza"
            facts.append(f"User {predicate} {obj}")
            
        return facts

    async def get_recent_facts(
        self,
        bot_name: str,
        limit: int = 15,
        hours: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent facts from the knowledge graph (for diary/dream generation).
        
        Returns facts across all users, optionally filtered by recency.
        
        Args:
            bot_name: The bot's name (for context)
            limit: Maximum number of facts to return
            hours: Optional - only get facts from last N hours
            
        Returns:
            List of fact dicts with subject, predicate, object
        """
        if not db_manager.neo4j_driver:
            return []
        
        try:
            # Build the query - get facts created by this bot
            if hours:
                query = """
                MATCH (u:User)-[r:FACT]->(o:Entity)
                WHERE r.learned_by = $bot_name
                  AND r.created_at >= datetime() - duration({hours: $hours})
                RETURN u.id as subject, r.predicate as predicate, o.name as object, 
                       r.confidence as confidence, r.created_at as created_at
                ORDER BY r.created_at DESC
                LIMIT $limit
                """
                params = {"bot_name": bot_name, "hours": hours, "limit": limit}
            else:
                query = """
                MATCH (u:User)-[r:FACT]->(o:Entity)
                WHERE r.learned_by = $bot_name
                RETURN u.id as subject, r.predicate as predicate, o.name as object,
                       r.confidence as confidence, r.created_at as created_at
                ORDER BY r.created_at DESC
                LIMIT $limit
                """
                params = {"bot_name": bot_name, "limit": limit}
            
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run(query, **params)
                records = await result.data()
                
                facts = []
                for r in records:
                    # Format user ID nicely
                    subject = r.get("subject", "someone")
                    if subject and len(subject) > 8:
                        subject = f"User_{subject[-4:]}"  # Just last 4 chars
                    
                    facts.append({
                        "subject": subject,
                        "predicate": r.get("predicate", "has"),
                        "object": r.get("object", "something"),
                        "confidence": r.get("confidence", 0.5),
                        "created_at": str(r.get("created_at")) if r.get("created_at") else None
                    })
                
                logger.debug(f"Found {len(facts)} recent facts for {bot_name}")
                return facts
                
        except Exception as e:
            logger.error(f"Failed to get recent facts: {e}")
            return []

    # ========== E30: AMBIENT GRAPH MEMORY SUPPORT ==========
    
    @require_db("neo4j", default_return=set())
    async def get_user_entities(self, user_id: str) -> set:
        """
        Get all entity names connected to a user.
        Used for ambient graph memory matching (Phase E30).
        
        Returns a set of entity names that the user has mentioned/connected to.
        This enables fast string matching against incoming messages.
        
        Example return: {"Luna", "Seattle", "marine biology", "sister Maya"}
        """
        cache_key = f"knowledge:user_entities:{user_id}"
        cached_data = await cache_manager.get_json(cache_key)
        if cached_data is not None:
            return set(cached_data)  # Convert cached list to set
        
        try:
            query = """
            MATCH (u:User {id: $user_id})-[:FACT]->(e:Entity)
            RETURN DISTINCT e.name as name
            """
            
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run(query, user_id=user_id)
                records = await result.data()
                
                entities = {r['name'] for r in records if r.get('name')}
                
                # Cache for 5 minutes (300 seconds) - use set_json for list serialization
                await cache_manager.set_json(cache_key, list(entities), ttl=300)
                
                logger.debug(f"[E30] Loaded {len(entities)} entities for user {user_id[:8]}...")
                return entities
                
        except Exception as e:
            logger.error(f"Failed to get user entities: {e}")
            return set()

    async def get_user_entity_count(self, user_id: str) -> int:
        """Get count of entities for a user (for instrumentation)."""
        entities = await self.get_user_entities(user_id)
        return len(entities)

    @require_db("neo4j", default_return=[])
    async def search_memories_in_graph(self, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for memories in the Knowledge Graph using string matching.
        This serves as a fallback/complement to vector search.
        
        Args:
            user_id: The user ID to search memories for
            query: The text string to search for (case-insensitive)
            limit: Max results
            
        Returns:
            List of dicts with memory content, timestamp, and vector_id
        """
        try:
            cypher = """
            MATCH (u:User {id: $user_id})-[:HAS_MEMORY]->(m:Memory)
            WHERE toLower(m.content) CONTAINS toLower($query)
            RETURN m.content as content, m.timestamp as timestamp, m.vector_id as vector_id
            ORDER BY m.timestamp DESC
            LIMIT $limit
            """
            
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run(cypher, user_id=user_id, query=query, limit=limit)
                records = await result.data()
                return records
        except Exception as e:
            logger.error(f"Failed to search memories in graph: {e}")
            return []


# Global instance
knowledge_manager = KnowledgeManager()
