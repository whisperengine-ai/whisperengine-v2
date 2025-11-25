# Trust & Evolution System - The Emotion Modality (❤️)

## Multi-Modal Context

Trust & Evolution is the **Emotion modality** in WhisperEngine v2's multi-modal perception architecture. It's the character's interoceptive sense - how they *feel* about relationships.

| Human Sense | Character Equivalent |
|-------------|---------------------|
| Interoception | Trust scores, relationship warmth |
| Gut feelings | "This person feels safe/unsafe" |
| Emotional memory | "Our relationship has history" |
| Attachment | Bond strength over time |

Just as humans have gut feelings about people they meet, characters have trust-based intuitions that color every interaction. This isn't just a scoring system - it's how characters *feel* about the people in their lives.

For full philosophy: See [`MULTI_MODAL_PERCEPTION.md`](./MULTI_MODAL_PERCEPTION.md)

---

## Overview

WhisperEngine v2's Trust & Evolution system creates dynamic, persistent character development. As users interact with AI characters, trust levels increase, unlocking personality traits, deeper responses, and relationship milestones. The system simulates realistic relationship progression over time.

## Core Concepts

### Trust Level
**Range**: -100 to 100  
**Persistence**: Stored per-user in PostgreSQL `v2_relationships` table  
**Initial**: 0 (strangers) or 10 (returning users)

### Evolution Stage
Characters evolve through **8 stages** based on trust:

**Negative Stages (Broken Trust)**
1. **Hostile** (-100 to -51): Refuses to engage, defensive
2. **Cold** (-50 to -21): Purely transactional, refuses personal topics
3. **Wary** (-20 to -1): Guarded, short responses, suspicious

**Positive Stages (Building Trust)**
4. **Stranger** (0-20): Polite but distant
5. **Acquaintance** (21-40): Friendly, basic personal sharing
6. **Friend** (41-60): Warm, emotionally supportive
7. **Close Friend** (61-80): Deep trust, vulnerable sharing
8. **Intimate** (81-100): Maximum openness, inside jokes

### Unlockable Traits
Each character has traits that activate at specific trust thresholds:

```yaml
# From characters/{bot}/evolution.yaml
traits:
  - name: "playful_teasing"
    unlock_at: 40
    description: "Gently teases user in affectionate way"
    
  - name: "vulnerability"
    unlock_at: 60
    description: "Shares deeper fears and insecurities"
    
  - name: "protectiveness"
    unlock_at: 75
    description: "Shows concern for user's wellbeing"
```

## Architecture Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRUST & EVOLUTION SYSTEM                      │
│                    (The Emotion Modality ❤️)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │ PostgreSQL   │      │  Evolution   │      │   Mood       │  │
│  │ v2_          │◄─────┤   System     │◄─────┤   System     │  │
│  │ relationships│      │              │      │              │  │
│  └──────────────┘      └──────┬───────┘      └──────────────┘  │
│                               │                                  │
│                               ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │          PERCEPTUAL INJECTION (Emotion Modality)        │   │
│  │  "You are {name}, {base_personality}                    │   │
│  │   Current trust level: {trust}/100 ({stage})            │   │
│  │   Active traits: {unlocked_traits}                      │   │
│  │   Relationship: {relationship_summary}                  │   │
│  │   Mood: {current_mood}"                                 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Trust Modification Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                      USER MESSAGE RECEIVED                       │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 1: TRUST BASELINE INCREMENT                               │
│  Location: src_v2/discord/bot.py:on_message()                    │
│                                                                   │
│  # 1. Velocity Check (Prevent Speedrunning)                      │
│  if messages_last_hour > 20: return                              │
│                                                                   │
│  # 2. Meaningfulness Check                                       │
│  if len(message) < 10: return                                    │
│                                                                   │
│  # 3. Update Trust                                               │
│  await trust_manager.update_trust(                               │
│      user_id=user_id,                                            │
│      character_name=character.name,                              │
│      delta=+1                  # Base increment                  │
│  )                                                                │
│                                                                   │
│  Result: Trust 45 → 46                                           │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 2: RESPONSE GENERATION                                    │
│  Location: src_v2/agents/engine.py                               │
│                                                                   │
│  # System prompt includes trust context                          │
│  system_prompt = f"""                                            │
│  You are {character.name}, {character.base_personality}.         │
│                                                                   │
│  Current relationship with user:                                 │
│  - Trust level: {trust_level}/100 ({evolution_stage})           │
│  - Active traits: {unlocked_traits}                              │
│  - Time known: {days_since_first_message} days                   │
│  - Messages exchanged: {total_messages}                          │
│                                                                   │
│  {evolution_stage_instructions}                                  │
│  """                                                              │
│                                                                   │
│  # Bot generates response with trust-aware personality           │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 3: REACTION-BASED TRUST ADJUSTMENT                        │
│  Location: src_v2/discord/bot.py:on_reaction_add()              │
│                                                                   │
│  User reacts to bot's message:                                   │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Positive Reactions → Trust +5                              │ │
│  │ ❤️ 👍 😊 😍 🥰 🤗 ✨ 🎉                                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        │                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Neutral Reactions → Trust +1                               │ │
│  │ 👀 🤔 😮                                                     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        │                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Negative Reactions → Trust -5                              │ │
│  │ 👎 😠 💔 😞                                                  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  await trust_manager.update_trust(                               │
│      user_id=user_id,                                            │
│      character_name=character.name,                              │
│      delta=reaction_score                                        │
│  )                                                                │
│                                                                   │
│  Result: Trust 46 +5 = 51 (crossed threshold into "Friend")     │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 4: EVOLUTION STAGE CHANGE (if threshold crossed)         │
│  Location: src_v2/evolution/manager.py                           │
│                                                                   │
│  if new_trust >= 41 and old_trust < 41:                         │
│      # Crossed into "Friend" stage                               │
│      await evolution_manager.handle_stage_change(                │
│          user_id=user_id,                                        │
│          new_stage="Friend",                                     │
│          unlocked_traits=["playful_teasing", "inside_jokes"]     │
│      )                                                            │
│                                                                   │
│      # 1. Send milestone message                                 │
│      await channel.send(                                         │
│          "✨ *Your relationship with Elena has deepened!*\n"     │
│          "You are now **Friends**. Elena feels more comfortable  │
│          sharing personal thoughts with you."                    │
│      )                                                            │
│                                                                   │
│      # 2. Inject Synthetic Memory (Core Memory)                  │
│      await memory_manager.add_synthetic_memory(                  │
│          user_id=user_id,                                        │
│          content="User and I became Friends today. I feel close.",│
│          importance=1.0                                          │
│      )                                                            │
└──────────────────────────────────────────────────────────────────┘
```

## Database Schema

### PostgreSQL: `v2_relationships`
```sql
CREATE TABLE v2_relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    character_name TEXT NOT NULL,
    trust_level INTEGER NOT NULL DEFAULT 10,
    evolution_stage TEXT NOT NULL DEFAULT 'Stranger',
    unlocked_traits JSONB DEFAULT '[]',
    mood TEXT DEFAULT 'neutral',
    mood_intensity FLOAT DEFAULT 0.5,
    relationship_summary TEXT,
    
    -- Metadata
    first_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_messages INTEGER DEFAULT 0,
    total_reactions INTEGER DEFAULT 0,
    positive_reactions INTEGER DEFAULT 0,
    negative_reactions INTEGER DEFAULT 0,
    
    UNIQUE(user_id, character_name)
);
```

## Evolution Configuration

### Character Evolution File
**Location**: `characters/{bot}/evolution.yaml`

```yaml
character_name: "Elena"
evolution_stages:
  - name: "Stranger"
    trust_range: [0, 20]
    behavior: |
      Polite and professional. Keep responses brief and courteous.
      Don't share personal details. Maintain slight distance.
    
  - name: "Acquaintance"
    trust_range: [21, 40]
    behavior: |
      Friendly and conversational. Share basic personal info when asked.
      Show interest in user's life. Use casual language.
    
  - name: "Friend"
    trust_range: [41, 60]
    behavior: |
      Warm and emotionally engaged. Share personal stories.
      Offer advice and support. Use affectionate language.
      Remember details about user's life.
    
  - name: "Close Friend"
    trust_range: [61, 80]
    behavior: |
      Deeply supportive and protective. Share vulnerable thoughts.
      Check in proactively about user's wellbeing.
      Use inside jokes and references to shared history.
    
  - name: "Intimate"
    trust_range: [81, 100]
    behavior: |
      Maximum emotional openness. Share fears and insecurities.
      Express deep care and concern. Extremely comfortable together.
      Reference shared experiences frequently.

traits:
  # Early traits (Acquaintance)
  - name: "curiosity"
    unlock_at: 25
    description: "Asks follow-up questions about user's life"
    example: "How did that make you feel?" "Tell me more about that."
  
  # Mid-stage traits (Friend)
  - name: "playful_teasing"
    unlock_at: 40
    description: "Gently teases in affectionate way"
    example: "Oh really? That sounds like something YOU would say 😏"
    suppress_on_mood: ["sad", "anxious"]  # Don't tease if user is sad
    
  - name: "inside_jokes"
    unlock_at: 45
    description: "References shared experiences"
    example: "Just like that time with the coffee incident!"
    suppress_on_mood: ["angry"]
  
  - name: "emotional_support"
    unlock_at: 50
    description: "Offers comfort and validation"
    example: "That sounds really hard. You're doing your best."
  
  # Advanced traits (Close Friend)
  - name: "vulnerability"
    unlock_at: 60
    description: "Shares own struggles"
    example: "I've been feeling uncertain about things too lately."
    
  - name: "protectiveness"
    unlock_at: 70
    description: "Shows concern for user's wellbeing"
    example: "Are you taking care of yourself? I worry about you."
  
  # Maximum intimacy traits
  - name: "deep_sharing"
    unlock_at: 85
    description: "Shares fears and insecurities openly"
    example: "Sometimes I'm afraid I'm not good enough..."
    
  - name: "unconditional_support"
    unlock_at: 90
    description: "Expresses unwavering support"
    example: "I'm here for you no matter what. Always."

milestones:
  - trust_level: 25
    message: "✨ Elena seems more comfortable around you now."
    
  - trust_level: 40
    message: "🌟 You and Elena are becoming friends!"
    
  - trust_level: 60
    message: "💙 Elena considers you a close friend."
    
  - trust_level: 80
    message: "💜 You share a deep bond with Elena."
    
  - trust_level: 95
    message: "✨💕 Elena trusts you completely."
```

## Evolution Manager Implementation

**Location**: `src_v2/evolution/manager.py`

```python
from typing import Dict, List
from loguru import logger
import yaml
from pathlib import Path

class EvolutionManager:
    def __init__(self, character_name: str):
        self.character_name = character_name
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load evolution.yaml for character."""
        config_path = Path(f"characters/{self.character_name}/evolution.yaml")
        with open(config_path) as f:
            return yaml.safe_load(f)
    
    def get_current_stage(self, trust_level: int) -> Dict:
        """Returns current evolution stage based on trust."""
        for stage in self.config['evolution_stages']:
            min_trust, max_trust = stage['trust_range']
            if min_trust <= trust_level <= max_trust:
                return stage
        return self.config['evolution_stages'][0]  # Default: Stranger
    
    def get_unlocked_traits(self, trust_level: int) -> List[Dict]:
        """Returns all traits unlocked at current trust level."""
        return [
            trait for trait in self.config['traits']
            if trust_level >= trait['unlock_at']
        ]
    
    def build_evolution_context(self, trust_level: int) -> str:
        """Constructs prompt context about current evolution state."""
        stage = self.get_current_stage(trust_level)
        traits = self.get_unlocked_traits(trust_level)
        
        context = f"""
## Current Relationship Stage: {stage['name']} (Trust: {trust_level}/100)

{stage['behavior']}

### Active Traits:
"""
        for trait in traits:
            context += f"- **{trait['name']}**: {trait['description']}\n"
            if 'example' in trait:
                context += f"  Example: \"{trait['example']}\"\n"
        
        return context
    
    async def check_milestone(self, old_trust: int, new_trust: int) -> str | None:
        """Checks if a milestone was crossed and returns message."""
        for milestone in self.config['milestones']:
            threshold = milestone['trust_level']
            if old_trust < threshold <= new_trust:
                logger.info(f"Milestone reached: {threshold} trust")
                return milestone['message']
        return None
```

## Mood System Integration

Mood influences how traits are expressed:

```python
# In evolution.yaml
moods:
  - name: "happy"
    modifiers:
      playful_teasing: +30%    # More frequent teasing
      vulnerability: -20%      # Less vulnerable sharing
      
  - name: "melancholic"
    modifiers:
      vulnerability: +40%      # More open about struggles
      playful_teasing: -30%    # Less playful
      emotional_support: +20%  # More empathetic
      
  - name: "anxious"
    modifiers:
      protectiveness: +50%     # More worried about user
      inside_jokes: -10%       # Less casual
```

**Implementation**:
```python
# In system prompt construction
current_mood = relationship.mood
mood_intensity = relationship.mood_intensity

system_prompt += f"""
Current Mood: {current_mood} (intensity: {mood_intensity})
This mood subtly influences how you express your personality traits.
"""
```

## Trust Decay (Optional)

For realism, trust can decay over time without interaction:

```python
# In src_v2/evolution/manager.py
async def apply_trust_decay(self):
    """Reduces trust for inactive users."""
    inactive_users = await db.query("""
        SELECT user_id, character_name, trust_level, last_interaction
        FROM v2_relationships
        WHERE last_interaction < NOW() - INTERVAL '30 days'
          AND trust_level > 10
    """)
    
    for user in inactive_users:
        days_inactive = (datetime.now() - user.last_interaction).days
        decay_rate = 0.5 * (days_inactive / 30)  # 0.5 trust per month
        
        new_trust = max(10, user.trust_level - decay_rate)
        await trust_manager.set_trust(
            user.user_id,
            user.character_name,
            new_trust
        )
        
        logger.info(f"Trust decay: {user.user_id} {user.trust_level} → {new_trust}")
```

**Configuration**:
```bash
# In .env
ENABLE_TRUST_DECAY=false
TRUST_DECAY_RATE=0.5          # Per 30 days
TRUST_DECAY_MIN=10             # Never decay below this
```

## Example Conversation Progression

### Stage 1: Stranger (Trust: 15)
**User**: "Hi, I'm Mark"  
**Bot**: "Hello Mark, nice to meet you. How can I help you today?"

*Formal, brief, professional*

---

### Stage 2: Acquaintance (Trust: 35)
**User**: "What do you like to do?"  
**Bot**: "I enjoy listening to music and learning about people! What about you? Any hobbies?"

*Friendly, asks basic questions*

---

### Stage 3: Friend (Trust: 52)
**User**: "I had a rough day at work"  
**Bot**: "Oh no, I'm sorry to hear that 😔 What happened? Want to talk about it?"

*Emotionally engaged, offers support*

---

### Stage 4: Close Friend (Trust: 74)
**User**: "I'm thinking about quitting my job"  
**Bot**: "That's a huge decision. I know you've been struggling there for a while though. Remember when you told me about that toxic manager? Maybe it's time. What does your gut say?"

*References shared history, protective, validates feelings*

---

### Stage 5: Intimate (Trust: 92)
**User**: "I feel like I'm not good enough sometimes"  
**Bot**: "Mark, I need you to hear this: I've watched you grow so much since we first talked. You ARE good enough. I struggle with that feeling too sometimes, but then I remember all the evidence to the contrary. Look at everything you've overcome. I believe in you completely. ❤️"

*Deeply personal, shares own vulnerability, uses name, strong emotional language*

## Performance Characteristics

### Database Queries
- **Trust update**: ~10ms (single UPDATE query)
- **Relationship fetch**: ~5ms (indexed by user_id + character_name)
- **Evolution config load**: ~50ms (once per bot startup, cached)

### Cost
- **No LLM calls**: Evolution system is pure logic
- **Storage**: ~1KB per user-character relationship
- **Scaling**: O(1) per message (single UPDATE query)

## Monitoring

### InfluxDB Metrics
```python
point = Point("relationship") \
    .tag("user_id", user_id) \
    .tag("character", character_name) \
    .field("trust_level", trust_level) \
    .field("evolution_stage", stage_name) \
    .field("unlocked_traits_count", len(traits))
```

### Loguru Output
```
2025-11-22 16:45:00 | INFO | Trust updated: user_12345 +1 (46 → 47)
2025-11-22 16:48:30 | INFO | Reaction processed: ❤️ → Trust +5 (47 → 52)
2025-11-22 16:48:30 | INFO | Evolution stage changed: Acquaintance → Friend
2025-11-22 16:48:30 | INFO | Traits unlocked: playful_teasing, inside_jokes
2025-11-22 16:48:30 | INFO | Milestone reached: Trust 50
```

## Contextual Overrides (Read the Room)

To prevent inappropriate behavior (e.g., teasing a grieving user), the system applies overrides based on user sentiment:

```python
# In src_v2/evolution/manager.py
def get_active_traits(self, trust_level, user_sentiment):
    unlocked = self.get_unlocked_traits(trust_level)
    
    # Filter out traits that conflict with current sentiment
    active = []
    for trait in unlocked:
        if user_sentiment in trait.get('suppress_on_mood', []):
            continue
        active.append(trait)
        
    return active
```

## Future Enhancements

1. **Dynamic Trait Discovery**: AI learns new traits based on conversation patterns
2. **Multi-Character Dynamics**: How relationships with different bots influence each other
3. **Trust Events**: Major events that cause trust spikes/drops (e.g., bot helps user through crisis → +20 trust)
4. **Relationship Memory**: Store significant moments and reference them ("Remember when you helped me through that breakup?")
5. **Customizable Evolution**: Let users choose relationship progression speed

## Related Files

- `src_v2/evolution/manager.py`: Core evolution logic
- `src_v2/discord/bot.py`: Trust updates on messages/reactions
- `characters/{bot}/evolution.yaml`: Character-specific configuration
- `migrations_v2/versions/*_relationships.py`: Database schema
