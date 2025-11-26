from typing import List, Optional
import yaml
from pathlib import Path
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from datetime import datetime
import time
from influxdb_client import Point

from src_v2.config.settings import settings
from src_v2.core.database import db_manager, retry_db_operation
from src_v2.core.cache import cache_manager
from src_v2.knowledge.extractor import FactExtractor, Fact
from src_v2.agents.llm_factory import create_llm
from src_v2.universe.privacy import privacy_manager

class KnowledgeManager:
    def __init__(self):
        self.extractor = FactExtractor()
        self.llm = create_llm(temperature=0.0)
        
        self.cypher_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert Neo4j Cypher developer.
Your task is to convert a natural language question into a Cypher query to retrieve information about a user OR the AI character.

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

RULES:
- ALWAYS use the parameter $user_id for the User node.
- ALWAYS use the parameter $bot_name for the Character node.
- If the query is ambiguous about the target (User vs Character), search BOTH.
- Return the relevant properties (usually o.name or r.predicate).
- Do NOT include markdown formatting (```cypher). Just the raw query.
- Use case-insensitive matching if unsure (e.g., toLower(r.predicate) = 'likes').
- For "hobbies" or "interests", ALWAYS check for 'LIKES', 'LOVES', 'ENJOYS'.
- If the question cannot be answered by the schema (e.g. asking for chat history, weather, time, or general knowledge), return exactly: RETURN "NO_ANSWER"

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
   Query: 
   MATCH (u:User {{id: $user_id}})-[r:FACT {{predicate: 'LIVES_IN'}}]->(o:Entity) DELETE r
   WITH u
   MERGE (new_loc:Entity {{name: 'Seattle'}})
   MERGE (u)-[:FACT {{predicate: 'LIVES_IN', confidence: 1.0}}]->(new_loc)

3. User: "Forget that I own a cat."
   Query: MATCH (u:User {{id: $user_id}})-[r:FACT]->(o:Entity) WHERE r.predicate = 'OWNS' AND o.name CONTAINS 'cat' DELETE r

RULES:
- Use $user_id parameter.
- Return ONLY the raw Cypher query. No markdown.
- Be careful with DELETE operations.
"""),
            ("human", "{correction}")
        ])
        self.correction_chain = self.correction_prompt | self.llm | StrOutputParser()

    async def initialize(self):
        """
        Initializes the Knowledge Graph schema (constraints and indexes).
        """
        if not db_manager.neo4j_driver:
            logger.warning("Neo4j driver not available. Skipping Knowledge Graph initialization.")
            return

        try:
            async with db_manager.neo4j_driver.session() as session:
                # Create constraints (which also create indexes)
                # User id must be unique
                await session.run("CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
                
                # Entity name should be indexed/unique
                await session.run("CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE")
                
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
                    """
                    await session.run(query, name=bot_name, obj=obj, predicate=predicate)
            
            logger.info(f"Successfully ingested background for {bot_name}.")

        except Exception as e:
            logger.error(f"Failed to ingest background for {bot_name}: {e}")

    async def query_graph(self, user_id: str, question: str, bot_name: str = "default") -> str:
        """
        Generates and executes a Cypher query based on a natural language question.
        """
        if not db_manager.neo4j_driver:
            return "Graph database not available."

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

            # Basic validation: Ensure it starts with a valid Cypher keyword
            valid_starts = ["MATCH", "CALL", "RETURN", "WITH", "OPTIONAL MATCH"]
            if not any(cypher_query.upper().startswith(keyword) for keyword in valid_starts):
                logger.warning(f"LLM generated invalid Cypher: {cypher_query}")
                return "Could not generate a valid graph query."

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

                result_str = "\n".join(connections) if connections else ""
                await cache_manager.set(cache_key, result_str)
                return result_str
        except Exception as e:
            logger.error(f"Common ground check failed: {e}")
            return ""

    async def search_bot_background(self, bot_name: str, user_message: str) -> str:
        """
        Checks if the user's message mentions anything related to the bot's background.
        """
        if not db_manager.neo4j_driver:
            return ""

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
    async def process_user_message(self, user_id: str, message: str, bot_name: str = "unknown"):
        """
        Extracts facts from the message and stores them in the Knowledge Graph.
        """
        if not settings.ENABLE_RUNTIME_FACT_EXTRACTION:
            return

        if not db_manager.neo4j_driver:
            return

        # 1. Extract Facts
        facts = await self.extractor.extract_facts(message)
        if not facts:
            return

        logger.info(f"Extracted {len(facts)} facts for user {user_id} (source: {bot_name})")

        # 2. Store in Neo4j
        async with db_manager.neo4j_driver.session() as session:
            for fact in facts:
                await session.execute_write(self._merge_fact, user_id, fact, bot_name)
        
        # Invalidate common ground cache for this user (across all bots)
        await cache_manager.delete_pattern(f"knowledge:common_ground:*:{user_id}")

    @staticmethod
    async def _merge_fact(tx, user_id: str, fact: Fact, bot_name: str):
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

        # 1. Handle Single Value Predicates (Global overwrite)
        if predicate in SINGLE_VALUE_PREDICATES:
            delete_query = """
            MATCH (u:User {id: $user_id})-[r:FACT {predicate: $predicate}]->()
            DELETE r
            """
            await tx.run(delete_query, user_id=user_id, predicate=predicate)

        # 2. Handle Antonyms (Specific object overwrite)
        if predicate in ANTONYM_PAIRS:
            antonyms = ANTONYM_PAIRS[predicate]
            # Delete relationships with antonym predicates to the SAME object
            delete_antonym_query = """
            MATCH (u:User {id: $user_id})-[r:FACT]->(o:Entity {name: $object_name})
            WHERE r.predicate IN $antonyms
            DELETE r
            """
            await tx.run(delete_antonym_query, 
                         user_id=user_id, 
                         object_name=fact.object, 
                         antonyms=antonyms)

        # 3. Merge New Fact
        query_safe = """
        MERGE (u:User {id: $user_id})
        MERGE (o:Entity {name: $object_name})
        MERGE (u)-[r:FACT {predicate: $predicate}]->(o)
        SET r.confidence = $confidence, r.source_bot = $bot_name, r.updated_at = datetime()
        """
        
        await tx.run(query_safe, 
                     user_id=user_id, 
                     object_name=fact.object, 
                     predicate=predicate,
                     confidence=fact.confidence,
                     bot_name=bot_name)

    async def get_user_knowledge(self, user_id: str, query: Optional[str] = None) -> str:
        """
        Retrieves relevant facts about the user from the Knowledge Graph.
        If query is provided, it generates a specific Cypher query.
        Otherwise, it returns general facts.
        """
        start_time = time.time()
        if not db_manager.neo4j_driver:
            return ""

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
                    # Limit to 10 most recent or relevant
                    result = await session.run("""
                        MATCH (u:User {id: $user_id})-[r:FACT]->(e:Entity)
                        RETURN r.predicate, e.name
                        ORDER BY r.created_at DESC
                        LIMIT 10
                    """, user_id=user_id)
                    
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

    async def clear_user_knowledge(self, user_id: str):
        """
        Deletes all facts associated with a user.
        """
        if not db_manager.neo4j_driver:
            return

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

# Global instance
knowledge_manager = KnowledgeManager()
