#!/usr/bin/env python3
"""
Emergence Observation Report Generator - 7 Day Analysis
Queries all data sources (PostgreSQL, Neo4j, Qdrant, InfluxDB) to analyze emergent behavior.
"""
import asyncio
import asyncpg
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json
from collections import defaultdict
from qdrant_client import QdrantClient
from neo4j import AsyncGraphDatabase
from influxdb_client import InfluxDBClient
import os
from loguru import logger

# Bot configurations
BOTS = [
    {"name": "elena", "port": 8000},
    {"name": "nottaylor", "port": 8008},
    {"name": "dotty", "port": 8002},
    {"name": "aria", "port": 8003},
    {"name": "dream", "port": 8004},
    {"name": "jake", "port": 8005},
    {"name": "marcus", "port": 8007},
    {"name": "ryan", "port": 8001},
    {"name": "sophia", "port": 8006},
    {"name": "gabriel", "port": 8009},
    {"name": "aethys", "port": 8010},
    {"name": "aetheris", "port": 8011},
]

class EmergenceAnalyzer:
    def __init__(self):
        self.pg_conn = None
        self.neo4j_driver = None
        self.neo4j_session = None
        self.qdrant_client = None
        self.influx_client = None
        self.lookback_days = 7
        self.cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
        
    async def connect_databases(self):
        """Connect to all data sources"""
        try:
            # PostgreSQL
            self.pg_conn = await asyncpg.connect(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=int(os.getenv('POSTGRES_PORT', '5432')),
                user=os.getenv('POSTGRES_USER', 'whisper'),
                password=os.getenv('POSTGRES_PASSWORD', 'password'),
                database=os.getenv('POSTGRES_DB', 'whisperengine_v2')
            )
            logger.info("✓ PostgreSQL connected")
            
            # Neo4j
            neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
            neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
            neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')
            self.neo4j_driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            self.neo4j_session = self.neo4j_driver.session()
            logger.info("✓ Neo4j connected")
            
            # Qdrant
            self.qdrant_client = QdrantClient(host="localhost", port=6333)
            logger.info("✓ Qdrant connected")
            
            # InfluxDB
            self.influx_client = InfluxDBClient(
                url="http://localhost:8086",
                token="my-super-secret-auth-token",
                org="whisperengine"
            )
            logger.info("✓ InfluxDB connected")
            
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
        
    async def close_connections(self):
        """Close all database connections"""
        if self.pg_conn:
            await self.pg_conn.close()
        if self.neo4j_session:
            await self.neo4j_session.close()
        if self.neo4j_driver:
            await self.neo4j_driver.close()
        if self.influx_client:
            self.influx_client.close()
            
    async def analyze_bot(self, bot_name: str) -> Dict[str, Any]:
        """Analyze emergent behavior for a single bot"""
        logger.info(f"\n{'='*60}\nAnalyzing: {bot_name.upper()}\n{'='*60}")
        
        # 1. Chat activity
        chat = await self.analyze_chat_activity(bot_name)
        
        # 2. Trust evolution
        trust = await self.analyze_trust_evolution(bot_name)
        
        # 3. Knowledge graph (FIXED!)
        knowledge = await self.analyze_knowledge_graph(bot_name)
        
        # 4. Memory patterns
        memory = await self.analyze_memory_patterns(bot_name)
        
        # 5. Autonomous behavior
        autonomous = await self.analyze_autonomous_behavior(bot_name)
        
        # 6. InfluxDB metrics (NEW!)
        influx_metrics = self.analyze_influx_metrics(bot_name)
        
        # Calculate emergence scores
        scores = self.calculate_emergence_scores(
            interactions=chat['total_interactions'],
            unique_users=chat['unique_users'],
            avg_trust=trust['average_trust'],
            entities=knowledge['entities'],
            bot_messages=autonomous['bot_messages'],
            total_messages=autonomous['total_messages']
        )
        
        return {
            'bot_name': bot_name,
            'chat_activity': chat,
            'trust_evolution': trust,
            'knowledge_graph': knowledge,
            'memory_patterns': memory,
            'autonomous_behavior': autonomous,
            'influx_metrics': influx_metrics,
            'emergence_scores': scores
        }
        
    async def analyze_chat_activity(self, bot_name: str) -> dict:
        """Analyze chat patterns."""
        query = """
        SELECT 
            COUNT(*) as total_messages,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(DISTINCT channel_id) as unique_channels,
            AVG(LENGTH(content)) as avg_message_length
        FROM v2_chat_history
        WHERE timestamp >= $1
        AND channel_id IN (
            SELECT DISTINCT channel_id FROM v2_chat_history WHERE character_name = $2
        )
        """
        row = await self.pg_conn.fetchrow(query, self.cutoff_date, bot_name)
        
        return {
            'total_interactions': row['total_messages'] or 0,
            'unique_users': row['unique_users'] or 0,
            'unique_channels': row['unique_channels'] or 0,
            'avg_message_length': float(row['avg_message_length'] or 0)
        }
        
    async def analyze_trust_evolution(self, bot_name: str) -> dict:
        """Analyze trust score changes."""
        query = """
        SELECT 
            COUNT(*) as total_relationships,
            AVG(trust_score) as avg_trust,
            COUNT(*) FILTER (WHERE trust_score = 100) as max_trust_users
        FROM v2_user_relationships
        WHERE character_name = $1
        """
        row = await self.pg_conn.fetchrow(query, bot_name)
        
        # Get trust distribution
        dist_query = """
        SELECT trust_score, COUNT(*) as count
        FROM v2_user_relationships
        WHERE character_name = $1
        GROUP BY trust_score
        ORDER BY trust_score DESC
        """
        dist_rows = await self.pg_conn.fetch(dist_query, bot_name)
        trust_distribution = {row['trust_score']: row['count'] for row in dist_rows}
        
        return {
            'total_relationships': row['total_relationships'] or 0,
            'average_trust': float(row['avg_trust'] or 0),
            'max_trust_users': row['max_trust_users'] or 0,
            'trust_distribution': trust_distribution
        }
        
    async def analyze_knowledge_graph(self, bot_name: str) -> dict:
        """Analyze knowledge graph growth (Neo4j) - FIXED QUERIES!"""
        try:
            # Get entity count
            entity_query = "MATCH (e:Entity) RETURN count(e) as count"
            entity_result = await self.neo4j_session.run(entity_query)
            entity_record = await entity_result.single()
            entity_count = entity_record['count'] if entity_record else 0
            
            # Get topic count
            topic_query = "MATCH (t:Topic) RETURN count(t) as count"
            topic_result = await self.neo4j_session.run(topic_query)
            topic_record = await topic_result.single()
            topic_count = topic_record['count'] if topic_record else 0
            
            # Get relationship count
            rel_query = "MATCH ()-[r:RELATED_TO|LINKED_TO]->() RETURN count(r) as count"
            rel_result = await self.neo4j_session.run(rel_query)
            rel_record = await rel_result.single()
            rel_count = rel_record['count'] if rel_record else 0
            
            # Get memory count
            mem_query = "MATCH (m:Memory) RETURN count(m) as count"
            mem_result = await self.neo4j_session.run(mem_query)
            mem_record = await mem_result.single()
            mem_count = mem_record['count'] if mem_record else 0
            
            return {
                'entities': entity_count,
                'topics': topic_count,
                'relationships': rel_count,
                'memory_nodes': mem_count
            }
        except Exception as e:
            logger.error(f"Knowledge graph analysis failed for {bot_name}: {e}")
            return {'entities': 0, 'topics': 0, 'relationships': 0, 'memory_nodes': 0}
        
    async def analyze_memory_patterns(self, bot_name: str) -> dict:
        """Analyze memory patterns (Qdrant)."""
        try:
            collection_name = f"whisperengine_memory_{bot_name}"
            collection_info = self.qdrant_client.get_collection(collection_name)
            total_memories = collection_info.points_count
            
            # Sample memories to analyze types
            if total_memories > 0:
                sample_size = min(100, total_memories)
                search_result = self.qdrant_client.scroll(
                    collection_name=collection_name,
                    limit=sample_size,
                    with_payload=True
                )
                
                points = search_result[0]
                type_counts = defaultdict(int)
                
                for point in points:
                    memory_type = point.payload.get('type') or point.payload.get('memory_type', 'unknown')
                    type_counts[memory_type] += 1
                
                # Calculate percentages
                type_percentages = {
                    mem_type: (count / len(points)) * 100 
                    for mem_type, count in type_counts.items()
                }
            else:
                type_percentages = {}
            
            return {
                'total_memories': total_memories,
                'type_distribution': type_percentages
            }
        except Exception as e:
            logger.error(f"Memory analysis failed for {bot_name}: {e}")
            return {'total_memories': 0, 'type_distribution': {}}
        
    async def analyze_autonomous_behavior(self, bot_name: str) -> dict:
        """Analyze bot autonomy using author_is_bot field."""
        try:
            query = """
            SELECT 
                COUNT(*) FILTER (WHERE author_is_bot = true) as bot_messages,
                COUNT(*) FILTER (WHERE author_is_bot = false) as user_messages
            FROM v2_chat_history
            WHERE character_name = $1
            AND timestamp >= $2
            """
            result = await self.pg_conn.fetchrow(query, bot_name, self.cutoff_date)
            bot_messages = result['bot_messages'] if result else 0
            user_messages = result['user_messages'] if result else 0
            total = bot_messages + user_messages
            
            # Get goal distribution
            goal_query = """
            SELECT category, COUNT(*) as count
            FROM v2_goals
            WHERE character_name = $1
            AND created_at >= $2
            GROUP BY category
            """
            goal_results = await self.pg_conn.fetch(goal_query, bot_name, self.cutoff_date)
            goals_by_category = {row['category']: row['count'] for row in goal_results}
            
            return {
                'bot_messages': bot_messages,
                'user_messages': user_messages,
                'total_messages': total,
                'bot_ratio': (bot_messages / total * 100) if total > 0 else 0,
                'goals_by_category': goals_by_category
            }
        except Exception as e:
            logger.error(f"Autonomous behavior analysis failed for {bot_name}: {e}")
            return {
                'bot_messages': 0,
                'user_messages': 0,
                'total_messages': 0,
                'bot_ratio': 0,
                'goals_by_category': {}
            }
    
    def analyze_influx_metrics(self, bot_name: str) -> dict:
        """Analyze InfluxDB metrics for feedback and engagement."""
        try:
            query_api = self.influx_client.query_api()
            
            # Get reaction metrics
            reaction_query = f'''
            from(bucket: "whisperengine")
                |> range(start: -{self.lookback_days}d)
                |> filter(fn: (r) => r["_measurement"] == "reactions")
                |> filter(fn: (r) => r["bot_name"] == "{bot_name}")
                |> group(columns: ["reaction_type"])
                |> count()
            '''
            
            reaction_result = query_api.query(reaction_query)
            reactions = {}
            total_reactions = 0
            for table in reaction_result:
                for record in table.records:
                    reaction_type = record.values.get('reaction_type', 'unknown')
                    count = record.get_value()
                    reactions[reaction_type] = count
                    total_reactions += count
            
            # Get response time metrics
            latency_query = f'''
            from(bucket: "whisperengine")
                |> range(start: -{self.lookback_days}d)
                |> filter(fn: (r) => r["_measurement"] == "response_time")
                |> filter(fn: (r) => r["bot_name"] == "{bot_name}")
                |> mean()
            '''
            
            latency_result = query_api.query(latency_query)
            avg_latency = 0
            for table in latency_result:
                for record in table.records:
                    avg_latency = record.get_value()
                    break
            
            return {
                'total_reactions': total_reactions,
                'reactions_by_type': reactions,
                'avg_response_time_ms': round(avg_latency, 2) if avg_latency else 0
            }
        except Exception as e:
            logger.error(f"InfluxDB metrics analysis failed for {bot_name}: {e}")
            return {
                'total_reactions': 0,
                'reactions_by_type': {},
                'avg_response_time_ms': 0
            }
    
    def calculate_emergence_scores(self, interactions: int, unique_users: int, 
                                  avg_trust: float, entities: int, 
                                  bot_messages: int, total_messages: int) -> dict:
        """Calculate weighted emergence scores."""
        # Social Engagement (30 points)
        max_interactions = 5000
        social_score = (min(interactions, max_interactions) / max_interactions) * 30
        
        # Relationship Depth (25 points) - Trust score (0-100 scale)
        trust_score = (avg_trust / 100) * 25
        
        # Knowledge Growth (25 points) - Entity count
        max_entities = 100
        knowledge_score = (min(entities, max_entities) / max_entities) * 25
        
        # Autonomy (20 points) - Bot message ratio
        autonomy_ratio = bot_messages / max(total_messages, 1)
        autonomy_score = autonomy_ratio * 20
        
        overall = social_score + trust_score + knowledge_score + autonomy_score
        return {
            'overall': round(overall, 2),
            'social': round(social_score, 2),
            'trust': round(trust_score, 2),
            'knowledge': round(knowledge_score, 2),
            'autonomy': round(autonomy_score, 2)
        }
    
    async def run_analysis(self):
        """Run analysis for all bots."""
        await self.connect_databases()
        
        all_bots = []
        for bot_config in BOTS:
            try:
                bot_report = await self.analyze_bot(bot_config['name'])
                all_bots.append(bot_report)
            except Exception as e:
                logger.error(f"Failed to analyze {bot_config['name']}: {e}")
                continue
        
        # Sort by emergence score
        all_bots.sort(key=lambda x: x['emergence_scores']['overall'], reverse=True)
        
        # Print report
        self.print_detailed_report(all_bots)
        
        # Save JSON
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"docs/research/emergence_report_{timestamp}.json"
        with open(output_file, 'w') as f:
            json.dump(all_bots, f, indent=2, default=str)
        logger.info(f"\n✓ Report saved to: {output_file}")
        
        await self.close_connections()
        return all_bots
    
    def print_detailed_report(self, all_bots: List[dict]):
        """Print detailed human-readable report."""
        print(f"\n{'='*80}")
        print(f"EMERGENCE OBSERVATION REPORT - {self.lookback_days} DAY ANALYSIS")
        print(f"Period: {self.cutoff_date.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'='*80}\n")
        
        # Rankings
        print("RANKINGS BY OVERALL EMERGENCE SCORE:\n")
        for i, bot in enumerate(all_bots, 1):
            scores = bot['emergence_scores']
            print(f"#{i}: {bot['bot_name'].upper():12} | Overall: {scores['overall']:5.2f} | "
                  f"Social: {scores['social']:5.2f} | Trust: {scores['trust']:5.2f} | "
                  f"Knowledge: {scores['knowledge']:5.2f} | Autonomy: {scores['autonomy']:5.2f}")
        
        # Detailed stats per bot
        print(f"\n{'='*80}")
        print("DETAILED BOT STATISTICS")
        print(f"{'='*80}\n")
        
        for i, bot in enumerate(all_bots, 1):
            print(f"#{i}: {bot['bot_name'].upper()}")
            print(f"  Emergence Score: {bot['emergence_scores']['overall']:.2f}/100")
            print()
            print(f"  Chat Activity:")
            print(f"    Total Interactions: {bot['chat_activity']['total_interactions']:,}")
            print(f"    Unique Users: {bot['chat_activity']['unique_users']}")
            print(f"    Channels: {bot['chat_activity']['unique_channels']}")
            print(f"    Avg Message Length: {bot['chat_activity']['avg_message_length']:.1f} chars")
            print()
            print(f"  Trust Evolution:")
            print(f"    Total Relationships: {bot['trust_evolution']['total_relationships']}")
            print(f"    Average Trust: {bot['trust_evolution']['average_trust']:.1f}/100")
            print(f"    Users at Max Trust: {bot['trust_evolution']['max_trust_users']}")
            print(f"    Trust Distribution: {bot['trust_evolution']['trust_distribution']}")
            print()
            print(f"  Knowledge Graph:")
            print(f"    Entities: {bot['knowledge_graph']['entities']:,}")
            print(f"    Topics: {bot['knowledge_graph']['topics']:,}")
            print(f"    Relationships: {bot['knowledge_graph']['relationships']:,}")
            print(f"    Memory Nodes: {bot['knowledge_graph']['memory_nodes']:,}")
            print()
            print(f"  Memory Patterns:")
            print(f"    Total Memories: {bot['memory_patterns']['total_memories']:,}")
            print(f"    Type Distribution: {bot['memory_patterns']['type_distribution']}")
            print()
            print(f"  Autonomous Behavior:")
            print(f"    Bot Messages: {bot['autonomous_behavior']['bot_messages']}")
            print(f"    User Messages: {bot['autonomous_behavior']['user_messages']}")
            print(f"    Bot Ratio: {bot['autonomous_behavior']['bot_ratio']:.2f}%")
            print(f"    Goals: {bot['autonomous_behavior']['goals_by_category']}")
            print()
            print(f"  InfluxDB Metrics:")
            print(f"    Total Reactions: {bot['influx_metrics']['total_reactions']}")
            print(f"    Reactions by Type: {bot['influx_metrics']['reactions_by_type']}")
            print(f"    Avg Response Time: {bot['influx_metrics']['avg_response_time_ms']}ms")
            print(f"\n{'-'*80}\n")

if __name__ == "__main__":
    analyzer = EmergenceAnalyzer()
    asyncio.run(analyzer.run_analysis())
