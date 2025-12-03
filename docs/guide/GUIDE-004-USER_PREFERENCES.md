# User Preferences: How Users Configure Bot Behavior

**Status**: ✅ Implemented  
**Version**: 2.2  
**Last Updated**: December 1, 2025

User Preferences allow users to customize how Elena (and other bots) interact with them. Unlike facts (which describe the user), preferences are **configuration settings** that the bot must respect.

**For injection details**, see [Cognitive Engine - User Feedback Patterns](../architecture/COGNITIVE_ENGINE.md#dynamic-context-injection).

## Overview

Preferences are explicit user instructions like:
- "Keep your responses short"
- "Call me Captain"
- "Stop using emojis"
- "Be more formal"

These are stored per-user-per-character and injected into every system prompt as **directives** the bot must follow.

---

## Architecture

### Data Storage (PostgreSQL)

Preferences are stored in the `preferences` JSONB column of `v2_user_relationships`:

```sql
CREATE TABLE v2_user_relationships (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    character_name VARCHAR(255) NOT NULL,
    trust_score INTEGER DEFAULT 0,
    preferences JSONB DEFAULT '{}',     -- ← Preferences stored here
    -- ... other columns ...
    UNIQUE(user_id, character_name)
);
```

Example preferences JSON:
```json
{
  "verbosity": "short",
  "style": "casual",
  "nickname": "Captain",
  "use_emojis": false,
  "topics_to_avoid": "politics"
}
```

### Supported Preference Keys

| Key | Type | Values | Description |
|-----|------|--------|-------------|
| `verbosity` | string | `"short"`, `"medium"`, `"long"`, `"dynamic"` | Response length |
| `style` | string | `"casual"`, `"formal"`, `"matching"` | Communication tone |
| `nickname` | string | Any name | What the bot calls the user |
| `use_emojis` | boolean | `true`, `false` | Whether to use emojis |
| `topics_to_avoid` | string | Topic description | Topics to steer away from |

Custom preferences can also be stored (any key-value pair).

---

## How Preferences Are Set

### Method 1: Explicit User Request (Cognitive Router)

When a user says "Keep your responses short", the Cognitive Router detects this and calls `UpdatePreferencesTool`:

```python
class UpdatePreferencesTool(BaseTool):
    name: str = "update_user_preferences"
    description: str = "Updates or deletes user preferences (configuration). Use this when the user explicitly changes a setting like 'stop calling me Captain' or 'change verbosity to short'."
    
    async def _arun(self, action: str, key: str, value: Optional[str] = None) -> str:
        if action == "delete":
            await trust_manager.delete_preference(self.user_id, self.character_name, key)
            return f"Deleted preference: {key}"
        elif action == "update":
            await trust_manager.update_preference(self.user_id, self.character_name, key, value)
            return f"Updated preference: {key} = {value}"
```

### Method 2: Automatic Extraction (PreferenceExtractor)

The `PreferenceExtractor` uses an LLM to detect implicit preference changes:

```python
class PreferenceExtractor:
    def __init__(self):
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert User Preference Analyst.
Your task is to extract explicit configuration preferences from user messages.

TARGET PREFERENCES:
1. **verbosity**: 'short', 'medium', 'long', 'dynamic' (e.g., "be concise", "give me detailed answers")
2. **style**: 'casual', 'formal', 'matching' (e.g., "talk to me like a friend", "be professional")
3. **nickname**: string (e.g., "call me Dave")
4. **topics_to_avoid**: string (e.g., "don't talk about politics")
5. **use_emojis**: boolean (e.g., "stop using emojis", "I love emojis")

RULES:
- Only extract preferences if the user EXPLICITLY requests a change in behavior.
- Ignore factual statements (use FactExtractor for those).
- Ignore transient requests (e.g., "write a short poem" is a task, not a preference).

EXAMPLES:
User: "Please keep your answers short."
Result: {{ "preferences": {{ "verbosity": "short" }} }}

User: "Call me Captain from now on."
Result: {{ "preferences": {{ "nickname": "Captain" }} }}

User: "I like pizza."
Result: {{ "preferences": {{}} }} (This is a fact, not a preference)
"""),
            ("human", "{input}")
        ])
    
    async def extract_preferences(self, text: str) -> Dict[str, Any]:
        """Extracts preferences from text. Returns a dictionary of key-value pairs."""
```

---

## How Preferences Are Stored

### TrustManager Methods

```python
class TrustManager:
    async def update_preference(self, user_id: str, character_name: str, key: str, value: Any):
        """Updates a specific preference setting."""
        async with db_manager.postgres_pool.acquire() as conn:
            json_value = json.dumps(value)
            await conn.execute("""
                UPDATE v2_user_relationships
                SET preferences = jsonb_set(COALESCE(preferences, '{}'::jsonb), $3::text[], $4::jsonb),
                    updated_at = NOW()
                WHERE user_id = $1 AND character_name = $2
            """, user_id, character_name, [key], json_value)
    
    async def delete_preference(self, user_id: str, character_name: str, key: str):
        """Deletes a specific preference setting."""
        async with db_manager.postgres_pool.acquire() as conn:
            await conn.execute("""
                UPDATE v2_user_relationships
                SET preferences = preferences - $3,
                    updated_at = NOW()
                WHERE user_id = $1 AND character_name = $2
            """, user_id, character_name, key)
    
    async def clear_user_preferences(self, user_id: str, character_name: str):
        """Clears all preferences for a user and character."""
        await conn.execute("""
            UPDATE v2_user_relationships
            SET preferences = '{}'::jsonb,
                updated_at = NOW()
            WHERE user_id = $1 AND character_name = $2
        """, user_id, character_name)
```

---

## How Preferences Are Injected Into the System Prompt

### Where It Happens

In `AgentEngine._format_relationship_context()`:

```python
def _format_relationship_context(self, relationship: Dict, current_mood: str, character_name: str) -> str:
    # ... trust/evolution context ...
    
    if relationship.get('preferences'):
        context += "\n[USER CONFIGURATION]\n"
        prefs = relationship['preferences']
        
        if 'verbosity' in prefs:
            v = prefs['verbosity']
            if v == 'short': 
                context += "- RESPONSE LENGTH: Keep responses very concise (1-2 sentences max).\n"
            elif v == 'medium': 
                context += "- RESPONSE LENGTH: Keep responses moderate (2-4 sentences).\n"
            elif v == 'long': 
                context += "- RESPONSE LENGTH: You may provide detailed, comprehensive responses.\n"
            elif v == 'dynamic': 
                context += "- RESPONSE LENGTH: Adjust length based on context and user's input length.\n"
        
        if 'style' in prefs:
            s = prefs['style']
            if s == 'casual': 
                context += "- TONE: Use casual, relaxed language. Slang is okay if fits character.\n"
            elif s == 'formal': 
                context += "- TONE: Maintain a formal, polite, and professional tone.\n"
            elif s == 'matching': 
                context += "- TONE: Mirror the user's energy and formality level.\n"
        
        # Other preferences handled generically
        for key, value in prefs.items():
            if key not in ['verbosity', 'style']:
                context += f"- {key}: {value}\n"
    
    return context
```

### Example System Prompt Injection

For a user with preferences:
```json
{
  "verbosity": "short",
  "style": "casual",
  "nickname": "Captain",
  "use_emojis": false
}
```

The system prompt includes:
```
[USER CONFIGURATION]
- RESPONSE LENGTH: Keep responses very concise (1-2 sentences max).
- TONE: Use casual, relaxed language. Slang is okay if fits character.
- nickname: Captain
- use_emojis: false
```

---

## Preferences Are Directives, Not Suggestions

Unlike common ground ("Feel free to reference...") or goals ("Try to naturally steer..."), preferences are **directives**:

| Injection | Instruction Type | Example |
|-----------|-----------------|---------|
| Common Ground | Permissive | "Feel free to reference them naturally" |
| Goals | Suggestive | "Try to naturally steer toward this goal" |
| **Preferences** | **Directive** | "Keep responses very concise (1-2 sentences max)" |

The bot **must** follow preferences. They're explicit user configuration.

---

## Real-World Examples

### Example 1: Verbosity Preference

**User**: "Your responses are too long. Keep it short."

**System detects**: `verbosity: "short"` preference

**System Prompt**:
```
[USER CONFIGURATION]
- RESPONSE LENGTH: Keep responses very concise (1-2 sentences max).
```

**Next user message**: "Tell me about coral reefs."

**Elena's response** (respecting preference):
> "Coral reefs are underwater ecosystems built by tiny animals called polyps. They're like the rainforests of the ocean! 🌊"

Instead of a 5-paragraph explanation, Elena keeps it to 2 sentences.

### Example 2: Nickname Preference

**User**: "Call me Captain from now on."

**System detects**: `nickname: "Captain"` preference

**System Prompt**:
```
[USER CONFIGURATION]
- nickname: Captain
```

**Next conversation**:

**User**: "Hey Elena!"

**Elena** (using nickname):
> "¡Hola, Captain! How's it going? What brings you to chat today?"

### Example 3: Style Preference

**User**: "I need you to be more professional. This is for work."

**System detects**: `style: "formal"` preference

**System Prompt**:
```
[USER CONFIGURATION]
- TONE: Maintain a formal, polite, and professional tone.
```

**Elena's response style changes**:
> "Good afternoon. I understand you're looking for professional assistance. How may I help you with your marine research inquiry today?"

### Example 4: Emoji Preference

**User**: "Please stop using so many emojis."

**System detects**: `use_emojis: false` preference

**System Prompt**:
```
[USER CONFIGURATION]
- use_emojis: false
```

**Elena's response** (no emojis):
> "Of course! I'll keep my messages emoji-free from now on. Just let me know if you change your mind."

---

## Preference Update Flow

### Scenario: User Says "Be more concise"

```
1. User sends: "Elena, can you be more concise? I don't need long explanations."
   ↓
2. Cognitive Router analyzes message
   ↓
3. Router detects preference change, calls UpdatePreferencesTool:
   - action: "update"
   - key: "verbosity"
   - value: "short"
   ↓
4. trust_manager.update_preference() called:
   UPDATE v2_user_relationships
   SET preferences = jsonb_set(preferences, ['verbosity'], '"short"')
   WHERE user_id = '123456789' AND character_name = 'elena'
   ↓
5. Response acknowledges: "Got it! I'll keep my responses shorter from now on."
   ↓
6. Next message: get_relationship_level() returns:
   {
     "preferences": {"verbosity": "short"},
     ...
   }
   ↓
7. System prompt includes:
   [USER CONFIGURATION]
   - RESPONSE LENGTH: Keep responses very concise (1-2 sentences max).
   ↓
8. Elena's responses are now shorter
```

---

## Preference Deletion Flow

### Scenario: User Says "Never mind, go back to normal responses"

```
1. User sends: "Actually, go back to your normal response length."
   ↓
2. Cognitive Router detects preference reset
   ↓
3. Router calls UpdatePreferencesTool:
   - action: "delete"
   - key: "verbosity"
   ↓
4. trust_manager.delete_preference() called:
   UPDATE v2_user_relationships
   SET preferences = preferences - 'verbosity'
   WHERE user_id = '123456789' AND character_name = 'elena'
   ↓
5. Response: "No problem! I'll go back to my regular style."
   ↓
6. Next message: No verbosity constraint in system prompt
   ↓
7. Elena responds with her default length (character.md default)
```

---

## Feedback-Derived Preferences

The `FeedbackAnalyzer` can also derive preferences from user behavior:

```python
async def analyze_user_feedback_patterns(self, user_id: str, days: int = 30) -> Dict:
    """
    Analyzes user's feedback patterns to detect preferences.
    
    Returns insights like:
    - "User prefers shorter responses" (if consistently reacts 👎 to long messages)
    - "User appreciates concise communication"
    """
    # Analyze reactions in InfluxDB
    # Look for patterns like: negative reactions on long messages
    
    if long_negative_ratio > 0.6:
        insights["verbosity_preference"] = "concise"
        insights["recommendations"].append("User prefers shorter responses")
```

These insights are shown as `[USER PREFERENCES (Derived from Feedback)]`:

```
[USER PREFERENCES (Derived from Feedback)]
- User prefers shorter responses
- User appreciates concise communication
```

This is separate from explicit preferences—it's behavioral inference.

---

## Difference: Explicit vs. Derived Preferences

| Type | Source | Storage | Instruction |
|------|--------|---------|-------------|
| **Explicit Preferences** | User says "be concise" | `preferences` JSONB | `[USER CONFIGURATION]` - Directive |
| **Derived Preferences** | User reacts 👎 to long messages | Feedback analysis | `[USER PREFERENCES (Derived)]` - Suggestion |

Explicit preferences are **directives**. Derived preferences are **suggestions**.

---

## Contrast with Other Data Types

| Data Type | Storage | Purpose | Mutability |
|-----------|---------|---------|------------|
| **Facts** | Neo4j (Knowledge Graph) | Information about user | Accumulates over time |
| **Preferences** | PostgreSQL (JSONB) | Configuration settings | User can update/delete |
| **Insights** | PostgreSQL (JSONB) | Psychological observations | Bot-generated |
| **Trust Score** | PostgreSQL | Relationship depth | Changes via interactions |

**Key distinction**: Facts describe who the user is. Preferences describe how the user wants to be treated.

---

## Preference Persistence

Preferences are **persistent across sessions**:
- Stored in PostgreSQL
- Loaded every time `get_relationship_level()` is called
- Remain until explicitly deleted by user

Unlike transient requests ("write me a short poem"), preferences are remembered permanently.

---

## Testing Preferences

```python
async def test_update_preference():
    """Test preference update."""
    await trust_manager.update_preference("test_user", "elena", "verbosity", "short")
    
    relationship = await trust_manager.get_relationship_level("test_user", "elena")
    assert relationship['preferences']['verbosity'] == "short"

async def test_delete_preference():
    """Test preference deletion."""
    # Set preference first
    await trust_manager.update_preference("test_user", "elena", "verbosity", "short")
    
    # Delete it
    await trust_manager.delete_preference("test_user", "elena", "verbosity")
    
    # Verify deletion
    relationship = await trust_manager.get_relationship_level("test_user", "elena")
    assert 'verbosity' not in relationship['preferences']

async def test_preference_extraction():
    """Test automatic preference extraction."""
    result = await preference_extractor.extract_preferences("Please keep your answers short.")
    
    assert 'verbosity' in result
    assert result['verbosity'] == "short"

async def test_fact_not_preference():
    """Test that facts are not extracted as preferences."""
    result = await preference_extractor.extract_preferences("I like pizza.")
    
    # This is a fact, not a preference
    assert result == {}
```

---

## Performance Considerations

### PostgreSQL Queries
- Preferences are loaded with `get_relationship_level()`: ~5-20ms
- Updates use `jsonb_set()`: ~10-20ms
- Deletions use `preferences - key`: ~10-20ms

### Caching Opportunities
- Preferences could be cached in Redis with TTL
- Current implementation loads fresh on every request (ensures consistency)

---

## Summary

User Preferences create personalized bot behavior through:

1. **Explicit Storage**: Key-value pairs in PostgreSQL JSONB
2. **Multiple Sources**: User requests (Router), automatic extraction (PreferenceExtractor)
3. **Directive Injection**: `[USER CONFIGURATION]` section with clear instructions
4. **Must-Follow Rules**: Unlike suggestions, preferences are mandatory
5. **Persistent**: Remembered across sessions until deleted
6. **Distinct from Facts**: Facts describe user; preferences describe desired behavior

The result is a bot that **respects user configuration** and adapts its communication style to individual preferences—verbosity, tone, nicknames, and more.
