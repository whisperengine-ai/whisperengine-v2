# Vision Pipeline - The Sight Modality (👁️)

**Version**: 2.2  
**Last Updated**: December 1, 2025

## Overview

The Vision Pipeline is the **Sight modality** in WhisperEngine v2's multi-modal perception architecture. It enables AI characters to **see** - perceiving and remembering images shared by users.

Just as humans process visual input through eyes → visual cortex → memory, characters process images through:
**Discord attachment → Multimodal LLM → Memory storage**

### Why Vision Matters

Without sight, characters are blind. They can't:
- See what users share (photos, memes, screenshots)
- React to visual content naturally
- Remember visual experiences
- Connect visual memories to conversations

Vision is a **first-class perceptual modality**, not a feature bolted onto a chatbot.

For full philosophy: See [`MULTI_MODAL_PERCEPTION.md`](./MULTI_MODAL_PERCEPTION.md)

## Architecture Components

### Core Components
1. **Vision Manager** (`src_v2/vision/manager.py`): Orchestrates image analysis
2. **LLM Vision Models**: GPT-4V, Claude 3 Opus/Sonnet, Gemini Pro Vision
3. **Memory Integration**: Stores visual memories in Qdrant with text embeddings
4. **Knowledge Extraction**: Extracts visual facts to Neo4j knowledge graph

### How Vision Integrates with Other Modalities

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VISION MODALITY INTEGRATION                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  👁️ VISION (This Pipeline)                                                  │
│  "I see a sunset over the ocean"                                            │
│        │                                                                    │
│        ├───────────────────┬─────────────────┐                              │
│        ▼                   ▼                 ▼                              │
│   🧠 MEMORY           🌌 UNIVERSE       ❤️ EMOTION                          │
│   "Store this         "Mark shared      "This feels                         │
│    visual memory"     this on Planet    nostalgic,                          │
│                       Lounge"           warm"                               │
│        │                   │                 │                              │
│        └───────────────────┴─────────────────┘                              │
│                            │                                                │
│                            ▼                                                │
│                   [INTEGRATED RESPONSE]                                     │
│                   Sees + Remembers + Knows context + Feels                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Complete Image Processing Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                      DISCORD IMAGE ATTACHMENT                    │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 1: ATTACHMENT DETECTION                                   │
│  Location: src_v2/discord/bot.py:on_message()                    │
│                                                                   │
│  if attachment.content_type.startswith("image/"):                │
│      image_urls.append(attachment.url)                           │
│      # Trigger background analysis                               │
│      if settings.LLM_SUPPORTS_VISION:                            │
│          asyncio.create_task(                                    │
│              vision_manager.analyze_and_store(                   │
│                  image_url, user_id, channel_id                  │
│              )                                                    │
│          )                                                        │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 2: VISION ANALYSIS                                        │
│  Location: src_v2/vision/manager.py:analyze_and_store()          │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 2.1 Image Download (if needed)                             │ │
│  │ - Discord CDN URLs are accessible directly                 │ │
│  │ - External URLs may need proxy/download                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        │                                          │
│                        ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 2.2 LLM Vision Analysis                                    │ │
│  │                                                             │ │
│  │ System Prompt:                                             │ │
│  │ "You are analyzing an image for {character_name}.          │ │
│  │  Describe what you see in detail. Include:                 │ │
│  │  - Main subjects/objects                                   │ │
│  │  - Setting/environment                                     │ │
│  │  - Colors, mood, atmosphere                                │ │
│  │  - Any text visible in the image                           │ │
│  │  - People (describe appearance, don't identify)            │ │
│  │  - Actions or events happening                             │ │
│  │                                                             │ │
│  │  Be thorough but concise."                                 │ │
│  │                                                             │ │
│  │ LLM: GPT-4V / Claude 3 Opus / Gemini Pro Vision            │ │
│  │ Input: [Image URL/Base64] + System Prompt                  │ │
│  │ Output: Detailed textual description                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        │                                          │
│                        ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 2.3 Entity Extraction (Optional)                           │ │
│  │                                                             │ │
│  │ If ENABLE_RUNTIME_FACT_EXTRACTION=true:                    │ │
│  │   Extract entities from description:                       │ │
│  │   - Objects: "cat", "laptop", "coffee mug"                 │ │
│  │   - Locations: "kitchen", "park", "office"                 │ │
│  │   - Activities: "working", "eating", "playing"             │ │
│  │                                                             │ │
│  │ Store to Neo4j:                                            │ │
│  │   (User)-[:SAW]->(Entity {type: "object", name: "cat"})   │ │
│  └────────────────────────────────────────────────────────────┘ │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 3: MEMORY STORAGE                                         │
│  Location: src_v2/vision/manager.py + memory/manager.py          │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 3.1 Create Visual Memory Record                            │ │
│  │                                                             │ │
│  │ memory_content = f"[Image: {description}]"                 │ │
│  │                                                             │ │
│  │ metadata = {                                               │ │
│  │     "type": "visual_memory",                               │ │
│  │     "image_url": image_url,                                │ │
│  │     "description": description,                            │ │
│  │     "channel_id": channel_id,                              │ │
│  │     "timestamp": datetime.now().isoformat(),               │ │
│  │     "extracted_entities": ["cat", "kitchen", ...]          │ │
│  │ }                                                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        │                                          │
│                        ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 3.2 Generate Text Embedding                                │ │
│  │                                                             │ │
│  │ # Use text description for semantic search                 │ │
│  │ embedding = await embedding_service.embed_query_async(     │ │
│  │     memory_content                                         │ │
│  │ )                                                           │ │
│  │                                                             │ │
│  │ # 384D vector from all-MiniLM-L6-v2                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        │                                          │
│                        ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 3.3 Store in Qdrant                                        │ │
│  │                                                             │ │
│  │ await qdrant_client.upsert(                                │ │
│  │     collection_name="whisperengine_memory_{bot_name}",     │ │
│  │     points=[PointStruct(                                   │ │
│  │         id=uuid4(),                                        │ │
│  │         vector=embedding,                                  │ │
│  │         payload=metadata                                   │ │
│  │     )]                                                      │ │
│  │ )                                                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 4: KNOWLEDGE GRAPH UPDATE                                 │
│  Location: src_v2/knowledge/manager.py                           │
│                                                                   │
│  If ENABLE_RUNTIME_FACT_EXTRACTION=true:                         │
│                                                                   │
│  Neo4j Graph:                                                    │
│  ┌──────────┐    ┌─────────────────────────────────────┐        │
│  │  User    │    │       SAW (relationship)            │        │
│  │  {id}    ├────┤  properties:                        │        │
│  └──────────┘    │  - image_url                        │        │
│                  │  - description                       │        │
│                  │  - timestamp                         │        │
│                  └─────────────┬───────────────────────┘        │
│                                │                                 │
│                                ▼                                 │
│                  ┌────────────────────────┐                      │
│                  │  Entity {type:"object"}│                      │
│                  │  name: "cat"           │                      │
│                  └────────────────────────┘                      │
└──────────────────────────────────────────────────────────────────┘
```

## Integration with Chat Flow

### During Message Processing

**Location**: `src_v2/discord/bot.py:on_message()` (lines 240-270)

```python
# 1. Collect all image URLs
image_urls = []
for attachment in message.attachments:
    if attachment.content_type and attachment.content_type.startswith("image/"):
        image_urls.append(attachment.url)
        logger.info(f"Detected image attachment: {attachment.url}")
        
        # 2. Trigger background analysis (fire-and-forget)
        if settings.LLM_SUPPORTS_VISION:
            asyncio.create_task(
                vision_manager.analyze_and_store(
                    image_url=attachment.url,
                    user_id=user_id,
                    channel_id=channel_id
                )
            )

# 3. Pass image URLs to agent engine for immediate context
response = await agent_engine.generate_response(
    character=character,
    user_message=user_message,
    chat_history=chat_history,
    context_variables=context_vars,
    user_id=user_id,
    image_urls=image_urls  # ← Used for real-time image discussion
)
```

### Real-Time vs Background Processing

**Real-Time (Immediate Response)**:
- Image URLs passed to LLM with user's message
- LLM can see and discuss image in current conversation
- Used when user says "What do you think of this photo?"

**Background (Memory Building)**:
- Vision analysis runs asynchronously
- Description stored for future retrieval
- Used for long-term memory and pattern recognition

## Vision Manager Implementation

**Location**: `src_v2/vision/manager.py`

```python
class VisionManager:
    def __init__(self):
        # Use vision-capable LLM
        self.llm = create_llm(
            temperature=0.3,
            model_name=settings.LLM_MODEL_NAME if settings.LLM_SUPPORTS_VISION else None
        )
        self.memory_manager = memory_manager
        self.knowledge_manager = knowledge_manager

    async def analyze_and_store(
        self, 
        image_url: str, 
        user_id: str, 
        channel_id: str
    ) -> Dict[str, Any]:
        """
        Analyzes an image and stores the results in memory + knowledge graph.
        
        Returns:
            {
                "description": str,
                "entities": List[str],
                "memory_id": str,
                "analysis_time_ms": float
            }
        """
        start_time = time.time()
        
        try:
            # 1. Analyze image with vision LLM
            description = await self._analyze_image(image_url)
            logger.info(f"Vision analysis complete: {description[:100]}...")
            
            # 2. Extract entities from description
            entities = []
            if settings.ENABLE_RUNTIME_FACT_EXTRACTION:
                entities = await self._extract_visual_entities(description)
                logger.debug(f"Extracted {len(entities)} entities from image")
            
            # 3. Store visual memory
            memory_id = await self._store_visual_memory(
                user_id=user_id,
                channel_id=channel_id,
                image_url=image_url,
                description=description,
                entities=entities
            )
            
            # 4. Update knowledge graph
            if entities and settings.ENABLE_RUNTIME_FACT_EXTRACTION:
                await self._update_knowledge_graph(
                    user_id=user_id,
                    image_url=image_url,
                    description=description,
                    entities=entities
                )
            
            analysis_time = (time.time() - start_time) * 1000
            logger.info(f"Vision pipeline complete in {analysis_time:.0f}ms")
            
            return {
                "description": description,
                "entities": entities,
                "memory_id": memory_id,
                "analysis_time_ms": analysis_time
            }
            
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return {
                "description": "[Image analysis failed]",
                "entities": [],
                "memory_id": None,
                "analysis_time_ms": 0
            }

    async def _analyze_image(self, image_url: str) -> str:
        """Uses vision LLM to generate detailed description."""
        prompt = """Analyze this image in detail. Describe:
- Main subjects/objects
- Setting and environment
- Colors and mood
- Any text visible
- People (describe appearance, don't identify)
- Actions or events

Be thorough but concise."""

        # LangChain vision message format
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        )
        
        response = await self.llm.ainvoke([message])
        return response.content

    async def _extract_visual_entities(self, description: str) -> List[str]:
        """Extract named entities from image description."""
        extraction_prompt = f"""Extract key entities from this image description.
        
Description: {description}

Return a JSON array of entities (objects, locations, activities).
Example: ["cat", "kitchen", "laptop", "coffee mug"]

Entities:"""

        response = await self.llm.ainvoke([HumanMessage(content=extraction_prompt)])
        
        try:
            # Parse JSON response
            entities = json.loads(response.content)
            return entities if isinstance(entities, list) else []
        except:
            # Fallback: simple word extraction
            return []

    async def _store_visual_memory(
        self, 
        user_id: str, 
        channel_id: str, 
        image_url: str, 
        description: str, 
        entities: List[str]
    ) -> str:
        """Stores visual memory in Qdrant."""
        memory_content = f"[Image: {description}]"
        
        metadata = {
            "type": "visual_memory",
            "image_url": image_url,
            "description": description,
            "extracted_entities": entities,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.memory_manager.add_message(
            user_id=user_id,
            character_name=settings.DISCORD_BOT_NAME,
            role='system',  # System-generated memory
            content=memory_content,
            channel_id=channel_id,
            metadata=metadata
        )
        
        return metadata.get('id', '')

    async def _update_knowledge_graph(
        self,
        user_id: str,
        image_url: str,
        description: str,
        entities: List[str]
    ):
        """Creates Neo4j relationships for visual entities."""
        for entity in entities:
            # Create SAW relationship
            cypher = """
            MATCH (u:User {id: $user_id})
            MERGE (e:Entity {name: $entity_name, type: 'visual'})
            MERGE (u)-[r:SAW {
                image_url: $image_url,
                description: $description,
                timestamp: datetime()
            }]->(e)
            """
            
            await self.knowledge_manager.execute_cypher(
                cypher,
                user_id=user_id,
                entity_name=entity,
                image_url=image_url,
                description=description[:200]  # Truncate for storage
            )
```

## Memory Retrieval

Visual memories are retrieved alongside text memories during semantic search:

```python
# In src_v2/memory/manager.py:search_memories()
results = await qdrant_client.search(
    collection_name=self.collection_name,
    query_vector=query_embedding,
    limit=10,
    score_threshold=0.7
)

# Results may include visual memories:
# {
#     "content": "[Image: A fluffy orange cat sitting on a laptop keyboard]",
#     "type": "visual_memory",
#     "image_url": "https://cdn.discordapp.com/attachments/...",
#     "score": 0.89
# }
```

## Example Conversation with Vision

**User**: *[Uploads photo of their cat]*  
**User**: "Meet Whiskers!"

**Bot Processing**:
1. Image detected → Background analysis starts
2. Vision LLM: "A fluffy orange tabby cat with green eyes, sitting on a gray couch"
3. Entity extraction: ["cat", "couch"]
4. Neo4j: `(User)-[:OWNS {name: "Whiskers"}]->(Entity {type: "pet", species: "cat"})`
5. Qdrant: Visual memory stored with description

**Bot Response** (immediate):  
"What a beautiful cat! Whiskers looks so fluffy and content on that couch. Those green eyes are stunning! 😻"

**Later Conversation**:  
**User**: "What does my cat look like again?"

**Bot Processing**:
1. Semantic search: "cat appearance"
2. Qdrant returns: "[Image: A fluffy orange tabby cat with green eyes...]"
3. Bot recalls specific details

**Bot Response**:  
"Whiskers is a fluffy orange tabby with gorgeous green eyes. I remember you showed me a photo of them looking super comfortable on your gray couch!"

## Supported Image Formats

- **JPEG/JPG**: Full support
- **PNG**: Full support
- **GIF**: First frame only (no animation analysis)
- **WebP**: Supported by most vision models
- **HEIC/HEIF**: May require conversion

## Cost Analysis

### Per Image Analysis
- **GPT-4V**: ~$0.01-0.05 per image (depends on resolution/tokens)
- **Claude 3 Opus**: ~$0.015-0.075 per image
- **Claude 3 Sonnet**: ~$0.003-0.015 per image (cheaper, good quality)
- **Gemini Pro Vision**: ~$0.0025-0.0125 per image (cheapest)

### Optimization Strategies

1. **Resolution Limits**: Downscale images >1024px to reduce tokens
2. **Batch Processing**: Analyze multiple images from same user together
3. **Caching**: Don't re-analyze same image URL
4. **Selective Analysis**: Only analyze if user references the image

## Configuration

```bash
# Enable/disable vision system
LLM_SUPPORTS_VISION=false

# Vision-capable model required
LLM_MODEL_NAME=gpt-4-vision-preview
# Or: claude-3-opus-20240229
# Or: claude-3-sonnet-20240229
# Or: gemini-1.5-pro

# Rate limiting
VISION_MAX_IMAGES_PER_MESSAGE=5
VISION_MAX_IMAGE_SIZE_MB=20

# Entity extraction
ENABLE_RUNTIME_FACT_EXTRACTION=true
```

## Error Handling

```python
# Image download fails
if not image_accessible:
    logger.warning(f"Could not access image: {image_url}")
    return {"description": "[Image unavailable]", ...}

# Vision LLM fails
try:
    description = await self._analyze_image(image_url)
except Exception as e:
    logger.error(f"Vision analysis error: {e}")
    description = "[Image analysis failed]"
    # Still store the image URL for future retry

# Entity extraction fails
try:
    entities = await self._extract_visual_entities(description)
except Exception as e:
    logger.warning(f"Entity extraction failed: {e}")
    entities = []  # Continue without entities
```

## Future Enhancements

1. **Video Analysis**: Frame-by-frame analysis of short videos
2. **OCR Extraction**: Dedicated text extraction from images (receipts, documents)
3. **Face Recognition**: Store face embeddings (privacy-aware)
4. **Image Generation Memory**: Remember images the bot generated
5. **Visual Search**: Search memories by image similarity (not just text)
6. **Multi-Image Context**: Analyze sequences of images together

## Related Files

- `src_v2/vision/manager.py`: Core vision processing
- `src_v2/discord/bot.py`: Image detection and triggering
- `src_v2/memory/manager.py`: Visual memory storage
- `src_v2/knowledge/manager.py`: Visual entity relationships
