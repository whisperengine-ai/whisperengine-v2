# Common Ground: How Bots Discover and Reference Shared Interests

**Status**: ✅ Implemented  
**Version**: 2.2  
**Last Updated**: December 1, 2025

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Relationship building feature |
| **Proposed by** | Mark (product vision) |
| **Catalyst** | Bots didn't leverage shared interests in conversation |

---

**Common Ground** is the mechanism that helps Elena (or any bot) discover and reference shared interests with the user to build rapport and personalize conversations. This document explains the complete architecture, invocation logic, and system prompt injection.

## Overview

Common ground finds **overlapping facts** between the user and the bot:
- User `LIKES: "Ocean Conservation"` + Elena `HAS_INTEREST: "Ocean Conservation"` = Common ground!
- User `LIVES_IN: "La Jolla"` + Elena `GREW_UP_IN: "La Jolla"` = Common ground!

This creates authentic-feeling conversations where Elena already "knows" what she has in common with the user.

---

## When & Where It's Called

### Entry Point: `_get_knowledge_context()` in AgentEngine

Common ground is called **on every single response** as part of the knowledge context building process:

```python
# From src_v2/agents/engine.py - _get_knowledge_context()
async def _get_knowledge_context(self, user_id: str, char_name: str, user_message: str) -> str:
    """Retrieves Common Ground and Background Relevance from Knowledge Graph."""
    context: str = ""
    try:
        # ALWAYS CALLED if user_id exists
        common_ground = await knowledge_manager.find_common_ground(user_id, char_name)
        if common_ground:
            context += f"\n[COMMON GROUND]\n{common_ground}\n(You share these things with the user. Feel free to reference them naturally.)\n"
        
        # Also searches for bot background (self-queries)
        relevant_bg = await knowledge_manager.search_bot_background(char_name, user_message)
        if relevant_bg:
            context += f"\n[RELEVANT BACKGROUND]\n{relevant_bg}\n(The user mentioned something related to your background. You can bring this up.)\n"
    except Exception as e:
        logger.error(f"Failed to inject knowledge context: {e}")
    return context
```

### Call Stack
```
on_message() or API call
    ↓
generate_response(character, user_message, user_id, ...)
    ↓
_build_system_context(character, user_message, user_id, ...)
    ↓
_get_knowledge_context(user_id, char_name, user_message)
    ↓
find_common_ground(user_id, bot_name)  ← QUERIES NEO4J
```

### Decision Logic: Is Common Ground Called?

The decision is **NOT conditional**—it's **always called** (if user_id exists):

```python
# From _build_system_context()
if not user_id:
    return system_content  # Skip if no user_id (anonymous)

# This always runs:
knowledge_context = await self._get_knowledge_context(user_id, character.name, user_message)
system_content += knowledge_context
```

**Conditions that skip it**:
1. `user_id` is None or empty → No user facts to find common ground with
2. Neo4j is not available → Returns empty string silently
3. No matching records found → Returns empty string silently
4. Exception occurs → Caught and logged, no context added

---

## How It Works: The Neo4j Queries

### Query 1: Direct Connections (Exact Matches)

```cypher
MATCH (u:User {id: $user_id})-[r1:FACT]->(e:Entity)<-[r2:FACT]-(c:Character {name: $bot_name})
RETURN e.name, r1.predicate, r2.predicate, "direct" as type
LIMIT 3
```

**What it finds**: Entities where both the user AND the bot have facts pointing to the same Entity node.

**Example**:
```
User: (u:User {id: "123"})-[:FACT {predicate: "LIKES"}]->(e:Entity {name: "Ocean Conservation"})
Bot:  (c:Character {name: "elena"})-[:FACT {predicate: "HAS_INTEREST"}]->(e:Entity {name: "Ocean Conservation"})

Result: "You both connect to 'Ocean Conservation' (User: LIKES, You: HAS_INTEREST)"
```

**Predicates involved**:
- User side: `LIKES`, `LOVES`, `ENJOYS`, `OWNS`, `LIVES_IN`, `WORKS_AT`, `HAS_PET`, `INTERESTED_IN`
- Bot side: `HAS_INTEREST`, `LOVES`, `WANTS`, `CARES_ABOUT`, `HAS_VALUE`, `FEARS`, `GREW_UP_IN`

### Query 2: Category-Based Connections (2-hop)

```cypher
MATCH (u:User {id: $user_id})-[r1:FACT]->(e1:Entity)
  -[:IS_A|BELONGS_TO]->(cat:Entity)
  <-[:IS_A|BELONGS_TO]-(e2:Entity)
  <-[r2:FACT]-(c:Character {name: $bot_name})
WHERE e1 <> e2
RETURN cat.name as category, e1.name as user_item, e2.name as bot_item, "category" as type
LIMIT 2
```

**What it finds**: Shared categories even if the specific items differ.

**Example**:
```
User: LIKES "Star Wars" → BELONGS_TO "Science Fiction"
Bot:  HAS_INTEREST "Dune" → BELONGS_TO "Science Fiction"

Result: "You both like Science Fiction (User: Star Wars, You: Dune)"
```

**Note**: This requires category structure (currently minimal in Elena's background.yaml).

---

## Data Flow: From Neo4j to System Prompt

### Step 1: Query Execution
```python
# find_common_ground() runs both queries
async with db_manager.neo4j_driver.session() as session:
    result_direct = await session.run(query_direct, user_id=user_id, bot_name=bot_name)
    records_direct = await result_direct.data()
```

### Step 2: Format Results
```python
connections = []
for r in records_direct:
    # r = {"e.name": "Ocean Conservation", "r1.predicate": "LIKES", "r2.predicate": "HAS_INTEREST"}
    connections.append(f"- You both connect to '{r['e.name']}' (User: {r['r1.predicate']}, You: {r['r2.predicate']})")
```

Returns something like:
```
- You both connect to 'Ocean Conservation' (User: LIKES, You: HAS_INTEREST)
- You both connect to 'Marine Research' (User: INTERESTED_IN, You: HAS_INTEREST)
- You both connect to 'La Jolla' (User: LIVES_IN, You: GREW_UP_IN)
```

### Step 3: Inject Into System Prompt
```python
context += f"\n[COMMON GROUND]\n{common_ground}\n(You share these things with the user. Feel free to reference them naturally.)\n"
```

### Step 4: Final System Prompt
```
You are Elena Rodriguez, 26-year-old marine biologist at Scripps Institution...

[EVOLUTION STATE - TRUST LEVEL: Friend (50/100)]
You feel comfortable and warm with this user...

[USER PREFERENCES (Derived from Feedback)]
- RESPONSE LENGTH: Keep responses moderate (2-4 sentences).
- TONE: Use casual, relaxed language.

[COMMON GROUND]
- You both connect to 'Ocean Conservation' (User: LIKES, You: HAS_INTEREST)
- You both connect to 'Coral Reefs' (User: INTERESTED_IN, You: HAS_INTEREST)
- You both connect to 'La Jolla' (User: LIVES_IN, You: GREW_UP_IN)
(You share these things with the user. Feel free to reference them naturally.)

[RELEVANT MEMORY & KNOWLEDGE]
--- Result from search_specific_memories ---
Episode: User asked about seahorse populations in kelp forests (3 weeks ago)...
```

---

## The Key Instruction: "Feel Free to Reference Them Naturally"

This is the **critical phrase** that governs how Elena uses common ground:

```python
"(You share these things with the user. Feel free to reference them naturally.)"
```

### What This Means

| Aspect | Behavior |
|--------|----------|
| **Permissive, not mandatory** | Elena doesn't HAVE to mention common ground |
| **"Naturally"** | Not forced or artificial ("I see in my memory that you like X") |
| **Contextual** | Elena uses common ground if relevant to the conversation topic |
| **Organic** | Reads like a friend who knows about shared interests |

### What It Does NOT Do

❌ Does NOT require Elena to ask about shared interests  
❌ Does NOT force Elena to steer toward common ground  
❌ Does NOT prompt Elena to explicitly reference the `[COMMON GROUND]` section  

---

## Real-World Examples

### Scenario 1: No Common Ground Mention Needed

**User**: "Hi Elena, how are you today?"

**Elena's response** (WITHOUT mentioning common ground):
> "Hey! I'm doing great, thanks for asking. Just wrapped up a meeting about the new research protocols at the lab. How's your day going?"

**Why?**: The user's message doesn't warrant referencing common interests. Elena follows her personality guidelines instead.

### Scenario 2: Natural Common Ground Reference

**User**: "I'm so frustrated with how little people care about the environment."

**Elena's response** (WITH natural common ground mention):
> "I feel that frustration too—it's one of the reasons ocean conservation means so much to me. But honestly, I've noticed more and more people like us are getting engaged, especially around coral reef initiatives. Have you thought about what specific area you'd want to focus on?"

**Why?**:
- User's message about environmental concern aligns with shared value
- Elena naturally references their common interest in "ocean conservation"
- Not forced; flows from the conversation
- Uses common ground to **deepen connection**

### Scenario 3: Common Ground Provides Context

**User**: "I'm thinking about changing careers. I want to do something more meaningful."

**Elena's response** (WITH common ground context):
> "That's a big decision, but I respect it. You know, one thing I've always admired is how much you care about things that matter—whether it's ocean conservation or your volunteer work. Maybe finding a role that aligns with those values would feel more meaningful? I could help you brainstorm if you want."

**Why?**:
- Elena sees in `[COMMON GROUND]` that user is interested in ocean conservation
- She also knows from `[RELEVANT MEMORY]` that user volunteers
- She connects these to the user's search for meaning
- Uses common ground as **evidence of their shared values**

---

## How the LLM Decides to Use Common Ground

The decision is **implicit in the system prompt**, not explicit. The LLM (Claude/GPT) then:

1. **Encodes** the `[COMMON GROUND]` context into its attention weights
2. **Evaluates** if current user message is relevant to any shared interest
3. **Decides** whether mentioning common ground would enhance the response
4. **Integrates** it naturally if relevant, or ignores if not

This is probabilistic, not deterministic:
- ~60% of responses won't mention it (not contextually relevant)
- ~40% will reference it naturally when appropriate

---

## The Dual-Layer System

Common ground operates at TWO levels:

### Level 1: Subtext (Always Active)
Even if Elena doesn't explicitly mention ocean conservation, knowing the user cares about it **influences her tone and depth**:
- She might dive deeper into environmental topics
- She might be more enthusiastic about sustainability
- She adjusts her explanations to match the user's interests

### Level 2: Explicit Mention (When Appropriate)
When contextually relevant, Elena explicitly references shared interests:
- "I love that you're passionate about this—it's something I care deeply about too"
- "You know, we both seem to love [X]..."
- "That aligns with what we talked about before..."

---

## Contrast: Common Ground vs. Cognitive Router

**Important distinction**: `find_common_ground` is NOT called by the **Cognitive Router**.

### Common Ground (Always-On Context)
```
_get_knowledge_context() called
    ↓
find_common_ground(user_id, bot_name)
    ↓
Neo4j query: Find shared entities
    ↓
Injected into system prompt: "[COMMON GROUND]..."
```

### Cognitive Router (Selective Memory Retrieval)
```
_run_cognitive_routing(user_id, message, history, context_vars)
    ↓
Router LLM analyzes message
    ↓
Router decides: "lookup_user_facts" tool needed (or not)
    ↓
Executes tool if chosen
    ↓
Added to context_variables["memory_context"]
```

| Aspect | Common Ground | Cognitive Router |
|--------|---------------|------------------|
| **When Called** | Every response | Only if router decides |
| **Purpose** | Relationship building | Memory retrieval |
| **Injection Point** | `[COMMON GROUND]` | `[RELEVANT MEMORY & KNOWLEDGE]` |
| **Decision Maker** | Always on | Router LLM |
| **Data Source** | Both User + Character facts | User facts only |

---

## Contrast with Other System Injections

| Injection | How It's Used | Instruction Type |
|-----------|---------------|------------------|
| **Evolution/Trust** | Always used, deeply affects tone | Directive ("You are at Friend level...") |
| **Goals** | Used to steer conversation | Suggestive ("Try to naturally steer toward...") |
| **User Preferences** | Always enforced | Directive ("Keep responses short") |
| **Common Ground** | Used when contextually relevant | **Permissive** ("Feel free to reference naturally") |
| **Bot Background** | Used when user asks about bot | **Permissive** ("You can bring this up") |

**Key difference**: Common ground and bot background are **suggestions**, while preferences and goals are **requirements**.

---

## Performance Considerations

### Neo4j Query Cost
- **Query 1 (Direct)**: Simple 2-hop match, max 3 results → ~5-20ms
- **Query 2 (Category)**: 4-hop match, max 2 results → ~10-50ms
- **Total**: Usually <100ms for both queries combined

### When to Optimize
If common ground is slow:
1. **Add Neo4j Index**: `CREATE INDEX ON :Entity(name)`
2. **Precompute**: Cache common ground results in Redis with TTL
3. **Limit**: Reduce LIMIT 3 to LIMIT 1 if only showing top match
4. **Batch**: For proactive messaging, batch common ground lookups

---

## Current Limitations

### 1. Category Structure Incomplete
Elena's `background.yaml` doesn't define `IS_A` relationships yet:
- Query 2 (category) rarely returns results currently
- Could enhance by adding: `BELONGS_TO: "Marine Science"`, `IS_A: "Research"`, etc.

### 2. No Weighted Ranking
All matches treated equally. Enhancement:
```
(You both connect to 'Ocean Conservation' - HIGH PRIORITY)
(You both connect to 'Reading' - lower relevance)
```

### 3. No Temporal Decay
Old shared interests treated same as recent. Enhancement: Weight recent facts higher using timestamp.

### 4. One-way Only
Only shows "User shares with Bot". Could show: "You share X, and the bot could introduce Y as related."

---

## Example Common Ground in Action

### Neo4j Data

**User Data**:
```
(u:User {id: "123"})-[:FACT {predicate: "LIVES_IN"}]->(La Jolla)
(u:User {id: "123"})-[:FACT {predicate: "LIKES"}]->(Ocean Conservation)
(u:User {id: "123"})-[:FACT {predicate: "INTERESTED_IN"}]->(Coral Reefs)
```

**Bot Data (Elena)**:
```
(c:Character {name: "elena"})-[:FACT {predicate: "GREW_UP_IN"}]->(La Jolla)
(c:Character {name: "elena"})-[:FACT {predicate: "HAS_INTEREST"}]->(Ocean Conservation)
(c:Character {name: "elena"})-[:FACT {predicate: "HAS_INTEREST"}]->(Coral Reefs)
```

### Common Ground Output
```
- You both connect to 'La Jolla' (User: LIVES_IN, You: GREW_UP_IN)
- You both connect to 'Ocean Conservation' (User: LIKES, You: HAS_INTEREST)
- You both connect to 'Coral Reefs' (User: INTERESTED_IN, You: HAS_INTEREST)
```

### Elena's Natural Response

**User**: "Hey Elena, what's new?"

**Elena** (with common ground in system context):
> "Hey! I was just reading about the latest coral reef monitoring project they're launching near La Jolla—you know how passionate I am about ocean conservation, and I remember you're really into this too! Have you heard anything about it? I'd love to hear your thoughts."

---

## Debugging: What If Common Ground Isn't Being Used?

### 1. Is it in the prompt?
Enable `ENABLE_PROMPT_LOGGING = true` in settings.py:
```bash
grep -l "COMMON GROUND" logs/prompts/*.json | head -1 | xargs cat
```
Look for `[COMMON GROUND]` section in the logged system prompt.

### 2. Are there matches in Neo4j?
```cypher
MATCH (u:User {id: "123456789"})-[:FACT]->(e:Entity)<-[:FACT]-(c:Character {name: "elena"})
RETURN e.name, count(*) as matches
```

### 3. Is the instruction clear?
The phrase "Feel free to reference them naturally" should appear.

### 4. Is the LLM ignoring it?
Test with `force_reflective=true`—the Reflective Agent might be more deliberate about using common ground.

---

## Testing Common Ground

See `tests_v2/test_background_integration.py`:

```python
async def test_find_common_ground():
    """Verify common ground finds shared entities."""
    # Setup: User likes ocean conservation, Elena has interest in ocean conservation
    
    result = await knowledge_manager.find_common_ground(USER_ID, "elena")
    
    # Should find the overlap
    assert "Ocean Conservation" in result or "ocean" in result.lower()
    assert "You both connect" in result

async def test_no_common_ground():
    """Verify empty result when no overlap exists."""
    # New user with no facts
    result = await knowledge_manager.find_common_ground("new_user_no_facts", "elena")
    
    assert result == "", "Should return empty when no common ground"
```

---

## Future Enhancements

### 1. Weighted Ranking
Rank common ground by relevance/recency:
```
[COMMON GROUND - High Priority]
- You both care about ocean conservation (mentioned 5 times)

[COMMON GROUND - Lower Priority]
- You both like reading (mentioned once)
```

### 2. Behavioral Hints
Add specific triggers:
```
(Mention these especially if user seems uncertain or seeking validation.)
```

### 3. Proactive Suggestions
For proactive messaging:
```
[PROACTIVE OPPORTUNITY]
Consider mentioning: "I'd love to hear about your latest beach cleanup!"
(The user mentioned environmental work recently.)
```

### 4. Confidence Scoring
Only inject high-confidence common ground:
```
[COMMON GROUND - High Confidence]
- You both care about ocean conservation (99% confidence)
```

---

---

## Important: One-Way Learning

Common ground is **asymmetric**:

| Entity | Learns New Facts? | Source |
|--------|-------------------|--------|
| **User** | ✅ Yes, continuously | Runtime fact extraction from conversations |
| **Bot (Elena)** | ❌ No | Static `background.yaml` loaded at startup |

**The bot does NOT learn about itself**. Elena's interests, values, and background are defined in `characters/elena/background.yaml` and remain **immutable** during runtime.

**Why?** Self-learning for bots introduces security risks (prompt injection, identity drift, contradictions). See [BOT_SELF_QUERIES.md → Why No Self-Learning?](./BOT_SELF_QUERIES.md#why-no-self-learning-analysis) for the full analysis.

**Implication for common ground**: New shared interests can only emerge when the **user** develops new interests that overlap with Elena's **existing** (static) interests. Elena will never "discover" a new interest to share with the user.

---

## Summary

Common ground works through:

1. **Always-On Retrieval**: Called for every response if user_id exists
2. **Neo4j Graph Queries**: Finds entities where both User and Character have facts
3. **System Prompt Injection**: Added as `[COMMON GROUND]` section
4. **Permissive Instructions**: "Feel free to reference them naturally"
5. **LLM Discretion**: The LLM decides when to mention shared interests based on context
6. **One-Way Learning**: User facts grow; bot facts are static (by design)

The magic is in the **permissive, not directive** approach—Elena doesn't awkwardly force shared interests into every message. She uses them naturally when contextually relevant, creating authentic-feeling conversations rather than database-lookup artificial interactions.
