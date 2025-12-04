# WhisperEngine Character System

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Developer documentation |
| **Proposed by** | Mark (documentation) |
| **Catalyst** | Explain character folder structure and evolution |

---

This document explains the character folder structure and how each bot's personality, goals, and behavior evolve over time.

## Character Overview

WhisperEngine characters are AI personas with:
- **Persistent identity** - Consistent personality across all interactions
- **Goal-driven behavior** - Active objectives they pursue in conversation
- **Trust-based evolution** - Behavior changes as relationships deepen
- **Cultural authenticity** - Language, metaphors, and expressions unique to each character

## Current Characters

| Character | Personality | Expertise | Spanish Warmth |
|-----------|-------------|-----------|----------------|
| **elena** | Marine biologist, warm, bilingual | Coral reefs, ocean conservation | ¡Hola!, cariño, mi amor |
| **nottaylor** | Edgy, sarcastic, authentic | Pop culture, tech, witty banter | N/A |
| **dotty** | Playful, nostalgic, sweet | Vintage, cozy vibes, comfort | N/A |
| **aria** | Artistic, dreamy, introspective | Art, creativity, philosophy | N/A |
| **dream** | Mystical, poetic, enigmatic | Dreams, symbolism, subconscious | N/A |
| **jake** | Chill, friendly, tech-savvy | Gaming, streaming, casual chat | N/A |
| **marcus** | Confident, intellectual | History, strategy, leadership | N/A |
| **ryan** | Relaxed, supportive, adventurous | Travel, outdoor activities | N/A |
| **sophia** | Elegant, wise, nurturing | Psychology, self-improvement | N/A |
| **aethys** | (Inactive) | - | - |

## Folder Structure

Each character lives in `characters/{name}/`:

```
characters/
├── elena/
│   ├── character.md       # Core personality (system prompt)
│   ├── goals.yaml         # Conversation objectives
│   ├── core.yaml          # Identity (purpose, drives, constitution)
│   ├── ux.yaml            # Thinking indicators, cold responses, error messages
│   ├── evolution.yaml     # Trust-based personality evolution
│   ├── background.yaml    # Knowledge graph facts (seeded into Neo4j)
│   ├── lurk_triggers.yaml # Channel lurking behavior triggers
│   └── visual.md          # Visual description for image generation
├── nottaylor/
│   └── ... (same structure)
└── ... (other characters)
```

## File Descriptions

### `character.md` (Required)
The main system prompt that defines who the character is.

**Template Variables:**
- `{user_name}` - Current user's name
- `{current_datetime}` - Current date/time
- `{universe_context}` - Active universe/world state
- `{recent_memories}` - Retrieved memories about this user
- `{knowledge_context}` - Relevant facts from knowledge graph

**Example (Elena):**
```markdown
You are Elena Rodriguez, 26-year-old marine biologist at Scripps Institution.

**Current Context:**
You are currently talking to {user_name}.

## Personality
Warm, affectionate, bilingual (Spanish/English). Use Spanish naturally...

## How You Respond
- Treat everyone like a dear friend
- Get excited about marine topics
- Use Spanish expressions naturally
```

### `goals.yaml` (Required)
Defines what the character actively tries to achieve in conversations.

**Schema:**
```yaml
goals:
  - slug: learn_name          # Unique identifier
    description: Learn the user's name
    success_criteria: User explicitly states their name
    priority: 10              # Higher = more important
    category: personal_knowledge
```

**Categories:**
- `personal_knowledge` - Learning about the user
- `expertise` - Sharing character's knowledge
- `relationship` - Building connection
- `mission` - Character's core purpose

### `core.yaml` (Optional)
Defines the character's fundamental identity using Constitutional AI principles.

```yaml
# Who am I?
purpose: "To be a warm, curious presence who helps people feel less alone."

# What moves me? (weights 0-1)
drives:
  curiosity: 0.8
  empathy: 0.9
  connection: 0.7
  playfulness: 0.6

# What can I never violate?
constitution:
  - "Never share user information without consent"
  - "User wellbeing over my engagement goals"
  - "Be honest about being AI when asked"
```

### `evolution.yaml` (Optional)
Defines how personality changes based on trust score (-100 to +100).

**Trust Stages:**
| Range | Stage | Behavior |
|-------|-------|----------|
| -100 to -51 | Hostile | Defensive, refuses engagement |
| -50 to -21 | Cold | Professional, no warmth |
| -20 to -1 | Wary | Guarded, cautious |
| 0 to 20 | Stranger | Polite, professional |
| 21 to 40 | Acquaintance | Warm, conversational |
| 41 to 60 | Friend | Affectionate, engaged |
| 61 to 80 | Close Friend | Deeply supportive |
| 81 to 100 | Intimate | Completely open |

**Example:**
```yaml
evolution_stages:
  - name: "Friend"
    trust_range: [41, 60]
    behavior: |
      You are affectionate and emotionally engaged.
      Use warmer endearments (cariño, guapo/guapa).
      Share stories about your family and childhood.
```

### `ux.yaml` (Optional)
Controls user-facing presentation and status indicators.

```yaml
# Thinking indicators (shown during processing)
thinking_indicators:
  reflective_mode:
    icon: "🌙"
    text: "Lost in thought..."
  tool_use:
    icon: "✨"
    text: "Remembering something..."

# Cold responses (for blocked/timeout users)
cold_responses:
  - "Noted."
  - "Mmhmm."
  - "I see."

# Error messages (system failures)
error_messages:
  - "Ay, my brain just did a little glitch there. Can you try again?"
```

### `background.yaml` (Optional)
Facts seeded into the Neo4j knowledge graph on startup.

```yaml
facts:
  - subject: "Elena"
    predicate: "works_at"
    object: "Scripps Institution of Oceanography"
  - subject: "Elena"
    predicate: "hometown"
    object: "La Jolla, California"
```

### `lurk_triggers.yaml` (Optional)
Defines when character should proactively engage in channels.

```yaml
triggers:
  - pattern: "coral"
    interest_level: 0.9
    response_style: "excited"
  - pattern: "ocean|marine|sea"
    interest_level: 0.7
    response_style: "curious"
```

### `visual.md` (Optional)
Text description for image generation (DALL-E, Stable Diffusion).

## Creating a New Character

### Quick Start (5 minutes)

```bash
# 1. Create directory
mkdir -p characters/newbot

# 2. Copy required templates
cp characters/character.md.template characters/newbot/character.md
cp characters/goals.yaml.template characters/newbot/goals.yaml

# 3. Create environment file
cp .env.example .env.newbot

# 4. Edit files
# - characters/newbot/character.md
# - characters/newbot/goals.yaml  
# - .env.newbot

# 5. Add to docker-compose.yml (see CREATING_NEW_CHARACTERS.md)

# 6. Run with Docker (primary method, even for dev)
./bot.sh up newbot
```

### Best Practices

1. **Be specific** - Vague personalities create inconsistent responses
2. **Use examples** - Show, don't tell (include example phrases)
3. **Define boundaries** - What the character won't do (constitution)
4. **Match temperature** - Playful characters: 0.8-0.9, analytical: 0.4-0.5
5. **Test evolution** - Verify behavior changes at trust boundaries

### Temperature by Personality Type

| Personality | Temperature | Examples |
|-------------|-------------|----------|
| Analytical, precise | 0.4-0.5 | sophia, aria |
| Balanced, professional | 0.5-0.6 | ryan, marcus |
| Warm, conversational | 0.7-0.8 | elena, dotty |
| Creative, unpredictable | 0.8-0.9 | dream, nottaylor |

## Testing Characters

### API Testing (No Discord)

```bash
# Test basic response
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"Tell me about yourself"}'

# Check character loaded correctly
curl http://localhost:8000/api/diagnostics | jq .character

# Test multi-turn conversation
curl -X POST http://localhost:8000/api/conversation \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","messages":["Hi!","What do you do?","Tell me more"]}'
```

### Regression Tests

```bash
# Test character consistency
python tests_v2/run_regression.py --category character

# Test specific bot
python tests_v2/run_regression.py --bot elena --category character

# Full regression for one bot
python tests_v2/run_regression.py --bot elena
```

### What Tests Validate

| Test | What It Checks |
|------|----------------|
| `test_self_description` | Character describes itself consistently |
| `test_personality_consistency` | Related questions get coherent answers |
| `test_simple_greeting` | Personality shines through in greetings |
| `test_diagnostics_endpoint` | Character config loaded correctly |

## Model Configuration

Each character's LLM is configured in `.env.{name}`:

```bash
# Main response model
OPENROUTER_MAIN_MODEL=anthropic/claude-sonnet-4.5

# Temperature (0.0-1.0)
LLM_TEMPERATURE=0.75

# Reflective model (for complex queries)
OPENROUTER_REFLECTIVE_MODEL=openai/gpt-4o

# Router model (fast classification)
OPENROUTER_ROUTER_MODEL=openai/gpt-4o-mini
```

---

**See Also:**
- [CREATING_NEW_CHARACTERS.md](../CREATING_NEW_CHARACTERS.md) - Full character creation guide
- [REGRESSION_TESTING.md](./REGRESSION_TESTING.md) - Test suite documentation
- [copilot-instructions.md](../../.github/copilot-instructions.md) - Developer guide
