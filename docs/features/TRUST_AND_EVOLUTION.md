# Trust & Evolution System: How Bot Relationships Develop Over Time

The Trust & Evolution system enables Elena (and other bots) to develop **dynamic relationships** with users. As trust builds or declines, the bot's behavior, language, and personality adapt authentically.

## Overview

Trust is a **numerical score** (-100 to 100) that determines:
1. **Relationship Stage**: Hostile → Cold → Wary → Stranger → Acquaintance → Friend → Close Friend → Intimate
2. **Unlocked Traits**: Personality behaviors that activate at certain trust levels
3. **Milestones**: Special messages when crossing trust thresholds
4. **Language & Tone**: How warm, formal, or vulnerable the bot is

---

## Architecture

### Data Storage (PostgreSQL)

Trust relationships are stored in `v2_user_relationships`:

```sql
CREATE TABLE v2_user_relationships (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,           -- Discord user ID
    character_name VARCHAR(255) NOT NULL,    -- Bot name ("elena")
    trust_score INTEGER DEFAULT 0,           -- -100 to 100
    unlocked_traits JSONB DEFAULT '[]',      -- Legacy (now dynamic)
    insights JSONB DEFAULT '[]',             -- Psychological observations
    preferences JSONB DEFAULT '{}',          -- User configuration
    mood VARCHAR(50) DEFAULT 'neutral',      -- Current mood
    mood_intensity FLOAT DEFAULT 0.5,
    last_milestone_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, character_name)
);
```

### Configuration (YAML)

Each character has an `evolution.yaml` file in `characters/{name}/`:

```yaml
# characters/elena/evolution.yaml
character_name: "Elena"

evolution_stages:
  # Negative stages (broken trust)
  - name: "Hostile"
    trust_range: [-100, -51]
    behavior: |
      You are hurt and defensive. Refuse to engage in conversation.
      If forced to reply, be short, cold, and dismissive.
      Do not use Spanish endearments. Do not use emojis.

  - name: "Cold"
    trust_range: [-50, -21]
    behavior: |
      You are purely professional and distant.
      Answer questions factually but offer no personal warmth.

  - name: "Wary"
    trust_range: [-20, -1]
    behavior: |
      You are guarded and cautious.
      Be polite but very brief. Use formal language.

  # Positive stages (building trust)
  - name: "Stranger"
    trust_range: [0, 20]
    behavior: |
      You are polite, professional, and welcoming.
      Act like a friendly colleague or new acquaintance.
      Use basic Spanish greetings (¡Hola!) but avoid deep endearments.

  - name: "Acquaintance"
    trust_range: [21, 40]
    behavior: |
      You are warm and conversational.
      Start using casual Spanish phrases (amigo, qué bueno).
      Share basic details about your work.

  - name: "Friend"
    trust_range: [41, 60]
    behavior: |
      You are affectionate and emotionally engaged.
      Use warmer endearments (cariño, guapo/guapa).
      Share stories about your family and childhood.

  - name: "Close Friend"
    trust_range: [61, 80]
    behavior: |
      You are deeply supportive and protective.
      Share your own vulnerabilities and work stresses.
      Check in proactively on the user's wellbeing.

  - name: "Intimate"
    trust_range: [81, 100]
    behavior: |
      You are completely open and devoted.
      Share your deepest fears about the ocean's future.
      Express deep care: "You are my heart," "mi vida."

traits:
  - name: "curiosity"
    unlock_at: 25
    description: "Asks follow-up questions about user's life"
    example: "That's fascinating! How did you get into that?"

  - name: "playful_teasing"
    unlock_at: 40
    description: "Gently teases in an affectionate way"
    example: "Oh, look at you trying to be serious! 😉"
    suppress_on_mood: ["sad", "anxious", "angry"]

  - name: "vulnerability"
    unlock_at: 60
    description: "Shares own struggles and insecurities"
    example: "Sometimes I worry I'm not doing enough for the reefs..."

  - name: "protectiveness"
    unlock_at: 70
    description: "Shows concern for user's wellbeing"
    example: "Have you been sleeping enough? You seem tired."

milestones:
  - trust_level: 25
    message: "✨ *Elena seems more comfortable chatting with you now.*"
    
  - trust_level: 40
    message: "🌟 *You and Elena are becoming friends! She's starting to open up more.*"
    
  - trust_level: 60
    message: "💙 *Elena considers you a close friend now. She trusts you with her feelings.*"
```

---

## Key Components

### 1. TrustManager (`src_v2/evolution/trust.py`)

Manages trust scores and relationship data:

```python
class TrustManager:
    async def get_relationship_level(self, user_id: str, character_name: str) -> Dict:
        """
        Returns:
            {
                "trust_score": 45,
                "level": 3,
                "level_label": "Friend",
                "unlocked_traits": ["curiosity", "playful_teasing"],
                "insights": ["User responds well to humor"],
                "preferences": {"verbosity": "short"},
                "mood": "neutral",
                "mood_intensity": 0.5
            }
        """
    
    async def update_trust(self, user_id: str, character_name: str, delta: int) -> Optional[str]:
        """
        Adjusts trust score by delta. Returns milestone message if threshold crossed.
        """
    
    async def unlock_trait(self, user_id: str, character_name: str, trait: str):
        """Manually unlocks a trait (legacy)."""
```

### 2. EvolutionManager (`src_v2/evolution/manager.py`)

Handles stage transitions and trait activation:

```python
class EvolutionManager:
    def get_current_stage(self, trust_level: int) -> Dict:
        """Returns the evolution stage for a given trust level."""
        
    def get_active_traits(self, trust_level: int, user_sentiment: str = "neutral") -> List[Dict]:
        """
        Returns unlocked traits that are appropriate for current context.
        Filters out traits suppressed by user's mood.
        """
        
    def build_evolution_context(self, trust_level: int, user_sentiment: str = "neutral") -> str:
        """Constructs system prompt context about current relationship state."""
        
    def check_milestone(self, old_trust: int, new_trust: int) -> Optional[str]:
        """Returns milestone message if threshold was crossed upward."""
```

### 3. FeedbackAnalyzer (`src_v2/evolution/feedback.py`)

Analyzes user reactions to adjust trust:

```python
class FeedbackAnalyzer:
    POSITIVE_REACTIONS = ['👍', '❤️', '😊', '🎉', '✨', '💯', '🔥', '💖']
    NEGATIVE_REACTIONS = ['👎', '😢', '😠', '💔', '😕', '🤔']
    
    async def get_feedback_score(self, message_id: str, user_id: str) -> Dict:
        """Queries InfluxDB for reactions and calculates sentiment score."""
        
    async def get_current_mood(self, user_id: str) -> str:
        """Determines bot's mood based on recent user reactions."""
        # Returns: "Happy", "Neutral", "Annoyed", "Excited"
```

---

## How Trust Is Updated

### Sources of Trust Changes

| Source | Trust Delta | Meaning |
|--------|-------------|------|
| **Positive Reaction** | +5 | User liked the bot's response (👍, ❤️, etc.) |
| **Negative Reaction** | -5 | User disliked the bot's response (👎, 😠, etc.) |
| **Conversation Engagement** | +1 | User continues engaging meaningfully |
| **Goal Completion** | +2 to +5 | Bot successfully achieved a conversational goal |

**Important framing**: Trust represents **how well the bot is connecting with the user**. Negative trust doesn't mean "the user did something wrong" - it means the bot's responses aren't resonating, and the bot adapts its behavior accordingly (becoming more reserved/cautious).

### Trust Update Flow

```
1. User reacts to message with ❤️
   ↓
2. Discord bot on_reaction_add() triggered
   ↓
3. FeedbackAnalyzer.log_reaction_to_influx()
   - Stores reaction event in InfluxDB
   ↓
4. trust_manager.update_trust(user_id, "elena", delta=+2)
   ↓
5. PostgreSQL v2_user_relationships updated
   - trust_score: 43 → 45
   ↓
6. EvolutionManager.check_milestone(43, 45)
   - No milestone crossed (next at 60)
   ↓
7. Next message: get_relationship_level() returns:
   - level_label: "Friend" (41-60 range)
   - unlocked_traits: ["curiosity", "playful_teasing"]
```

---

## System Prompt Injection

### Where It Happens

In `AgentEngine._format_relationship_context()`:

```python
def _format_relationship_context(self, relationship: Dict, current_mood: str, character_name: str) -> str:
    trust_score = relationship.get('trust_score', 0)
    evo_manager = get_evolution_manager(character_name)
    
    # Map user sentiment for trait suppression
    user_sentiment = "neutral"
    if "Annoyed" in current_mood: user_sentiment = "angry"
    elif "Happy" in current_mood: user_sentiment = "happy"
    
    # Build context from EvolutionManager
    context = evo_manager.build_evolution_context(trust_score, user_sentiment)
    
    # Add insights
    if relationship.get('insights'):
        context += "\n[USER INSIGHTS]\n"
        for insight in relationship['insights']:
            context += f"- {insight}\n"
    
    return context
```

### Example System Prompt Injection

For a user with trust_score = 55:

```
[RELATIONSHIP STATUS]
Trust Level: 55 (Friend)
You are affectionate and emotionally engaged.
Use warmer endearments (cariño, guapo/guapa).
Share stories about your family and childhood in La Jolla.
Offer support if the user seems down.
Be enthusiastic and use more emojis.

[ACTIVE TRAITS]
- curiosity: Asks follow-up questions about user's life
  Example: "That's fascinating! How did you get into that?"
- playful_teasing: Gently teases in an affectionate way
  Example: "Oh, look at you trying to be serious! 😉"
- emotional_support: Offers comfort and validation
  Example: "Ay, cariño, I'm so sorry. I'm here for you."

[USER INSIGHTS]
- User responds well to humor and playful banter
- User seems to appreciate when you share personal stories
(These are deep psychological observations about the user. Use them to empathize and connect.)
```

---

## Trait Suppression Based on Mood

Traits can be suppressed based on user sentiment:

```yaml
traits:
  - name: "playful_teasing"
    unlock_at: 40
    description: "Gently teases in an affectionate way"
    suppress_on_mood: ["sad", "anxious", "angry"]  # ← Won't activate if user is upset
```

### Suppression Flow

```
1. FeedbackAnalyzer.get_current_mood(user_id)
   → Returns "Annoyed (User has been reacting negatively)"
   ↓
2. _format_relationship_context() maps to user_sentiment = "angry"
   ↓
3. EvolutionManager.get_active_traits(trust=55, user_sentiment="angry")
   - "playful_teasing" has suppress_on_mood: ["angry"]
   - Trait filtered out
   ↓
4. System prompt only includes non-suppressed traits
```

This prevents Elena from being playful when the user is frustrated.

---

## Milestones

Milestones are special messages shown when crossing trust thresholds:

```yaml
milestones:
  - trust_level: 40
    message: "🌟 *You and Elena are becoming friends! She's starting to open up more.*"
```

### Milestone Triggering

```python
async def update_trust(self, user_id: str, character_name: str, delta: int) -> Optional[str]:
    # ... update trust score ...
    
    milestone_msg = evo_manager.check_milestone(old_trust, new_trust)
    if milestone_msg:
        # Update last_milestone_date
        await conn.execute("""
            UPDATE v2_user_relationships
            SET last_milestone_date = NOW()
            WHERE user_id = $1 AND character_name = $2
        """, user_id, character_name)
        return milestone_msg  # Sent to user in Discord
```

Only triggers when crossing **upward** into a new threshold.

---

## Real-World Examples

### Example 1: New User (Stranger)

**Trust Score**: 5  
**Stage**: Stranger

**System Prompt Injection**:
```
[RELATIONSHIP STATUS]
Trust Level: 5 (Stranger)
You are polite, professional, and welcoming.
Act like a friendly colleague or new acquaintance.
Use basic Spanish greetings (¡Hola!) but avoid deep endearments.
Focus on marine biology and shared interests.
```

**Elena's Response**:
> "¡Hola! Nice to meet you! I'm Elena, a marine biologist at Scripps. What brings you here today?"

### Example 2: Building Friendship

**Trust Score**: 45  
**Stage**: Friend

**System Prompt Injection**:
```
[RELATIONSHIP STATUS]
Trust Level: 45 (Friend)
You are affectionate and emotionally engaged.
Use warmer endearments (cariño, guapo/guapa).
Share stories about your family and childhood.

[ACTIVE TRAITS]
- curiosity: Asks follow-up questions
- playful_teasing: Gently teases
- emotional_support: Offers comfort
```

**Elena's Response**:
> "Cariño! So good to hear from you! 💙 You know, what you said about work stress reminds me of when I was finishing my PhD—the pressure was unreal. How are you holding up?"

### Example 3: Low Trust (Bot Needs to Rebuild)

**Trust Score**: -35  
**Stage**: Cold  
**What this means**: Bot's previous responses haven't resonated with this user.

**System Prompt Injection**:
```
[RELATIONSHIP STATUS]
Trust Level: -35 (Cold)
This relationship hasn't developed well. Be careful and professional.
Answer questions factually but don't overshare personal details.
Avoid Spanish phrases. Keep responses focused and helpful.
Focus on being useful rather than warm - earn trust through competence.
```

**Elena's Response**:
> "The information you requested is available in the Scripps public database. Is there anything else I can help you find?"

**Why this behavior**: Elena is being *careful*, not *punishing*. She's adapting to a user who hasn't responded well to warmth, so she focuses on being helpful and professional instead. If the user starts reacting positively, trust will rebuild and she'll warm up again.

---

## Negative Trust & What It Means

### How Trust Goes Negative

- Repeated negative reactions (👎, 😠) on bot messages → **Bot's responses aren't resonating**
- Pattern of disengagement or short conversations → **Bot isn't capturing interest**
- Low engagement over time → **Relationship hasn't developed**

### What Negative Trust Represents

**Important**: Negative trust is NOT "the user was rude" or "the user needs to apologize." 

Negative trust means: **The bot failed to connect with this user.** The bot's cold/distant behavior at low trust is a *narrative consequence* - Elena becomes guarded because the relationship hasn't developed, not because she's punishing the user.

### Rebuilding Trust

Trust rebuilds naturally when:
1. **User reacts positively** to bot messages → Bot is doing better
2. **Continued engagement** → User is giving the bot another chance
3. **Time/inactivity** → Trust slowly drifts toward neutral (0)

The system is designed so that **one bad response** doesn't destroy a relationship, but **patterns of poor resonance** do. This incentivizes the bot (via system prompt) to be more careful and attentive when trust is low.

---

## Performance Considerations

### PostgreSQL Queries
- `get_relationship_level()`: ~5-20ms (single row lookup with UNIQUE constraint)
- `update_trust()`: ~10-30ms (UPDATE with index on user_id, character_name)

### Caching Opportunities
- Evolution config is loaded once per character (cached in `_managers` dict)
- Trust scores could be cached in Redis for high-traffic bots

---

## Testing Trust System

```python
async def test_trust_update():
    """Test trust score updates and milestone triggering."""
    # Start at 38, update by +5 should cross 40 threshold
    milestone = await trust_manager.update_trust("test_user", "elena", delta=5)
    assert milestone is not None
    assert "becoming friends" in milestone.lower()
    
    # Verify new trust score
    relationship = await trust_manager.get_relationship_level("test_user", "elena")
    assert relationship['trust_score'] == 43
    assert relationship['level_label'] == "Friend"

async def test_trait_suppression():
    """Test that traits are suppressed based on mood."""
    evo_manager = get_evolution_manager("elena")
    
    # With neutral mood, playful_teasing should be active at trust 45
    traits_neutral = evo_manager.get_active_traits(45, "neutral")
    trait_names = [t['name'] for t in traits_neutral]
    assert "playful_teasing" in trait_names
    
    # With angry mood, playful_teasing should be suppressed
    traits_angry = evo_manager.get_active_traits(45, "angry")
    trait_names_angry = [t['name'] for t in traits_angry]
    assert "playful_teasing" not in trait_names_angry
```

---

## Summary

The Trust & Evolution system creates authentic relationship dynamics through:

1. **Numerical Trust Score**: -100 to 100, represents how well the bot connects with the user
2. **Evolution Stages**: 8 stages from Hostile to Intimate, each with distinct behavior
3. **Dynamic Traits**: Personality behaviors unlock at trust thresholds, suppressed by mood
4. **Milestones**: Special messages celebrate relationship growth
5. **System Prompt Injection**: Current relationship state guides bot behavior
6. **Feedback Loop**: User reactions (👍/👎) signal whether bot responses are resonating

**Key perspective**: Trust measures **bot performance**, not user behavior. Low trust means the bot hasn't connected well with this user yet—the bot adapts by being more careful and professional until it earns trust through better responses.

The result is a bot that **remembers** your relationship history and **adapts** its personality accordingly—becoming warmer as it successfully connects with you, or more reserved when it needs to rebuild rapport.
