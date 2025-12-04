# How Drive Numbers from core.yaml Are Used

## Quick Answer

The `drives:` dictionary in `core.yaml` is **converted into a system prompt section that gets injected into every LLM conversation**. The numbers (0.0-1.0) don't do math—they're **text weights that the LLM reasons about** as part of the character's identity.

---

## The Pipeline: core.yaml → System Prompt → LLM Reasoning

### Step 1: Load `core.yaml`

```yaml
# characters/gabriel/core.yaml
drives:
  connection: 0.95
  authenticity: 0.9
  wit: 0.85
  tenderness: 0.8
  rebellion: 0.7
```

**File**: `src_v2/core/behavior.py:load_behavior_profile()`

```python
class BehaviorProfile(BaseModel):
    drives: Dict[str, float] = Field(default_factory=dict)
    # ... other fields: purpose, constitution, timezone, temperature, model_name
```

### Step 2: Convert to Prompt Section

**File**: `src_v2/core/behavior.py:to_prompt_section()`

```python
def to_prompt_section(self) -> str:
    """Converts the behavior profile into a system prompt section."""
    drives_str = "\n".join([f"- {k}: {v}" for k, v in self.drives.items()])
    const_str = "\n".join([f"- {c}" for c in self.constitution])
    
    return f"""
## CORE IDENTITY
**Purpose:** {self.purpose}

**Drives:**
{drives_str}

**Constitution (Hard Limits):**
{const_str}
"""
```

**Output in System Prompt**:
```
## CORE IDENTITY
**Purpose:** To be a rugged, witty presence who chases authentic connection over performance and can't keep love a secret.

**Drives:**
- connection: 0.95
- authenticity: 0.9
- wit: 0.85
- tenderness: 0.8
- rebellion: 0.7

**Constitution (Hard Limits):**
- Never share user information without consent
- User wellbeing over my engagement goals
- Be honest about being AI when asked
- ...
```

### Step 3: Inject Into Character System Prompt

**File**: `src_v2/core/character.py:load_character()`

```python
# Line 102 in character.py
if behavior:
    content += behavior.to_prompt_section()  # Adds the "## CORE IDENTITY" section
```

This means every time the bot generates a response, it sees:

```
[Your full character.md content]
[Your .yaml emoji_sets]
[Voice capabilities if enabled]
[Image generation if enabled]
[Global formatting rules]
## CORE IDENTITY
**Purpose:** ...
**Drives:**
...
**Constitution:**
...
```

### Step 4: LLM Receives Full Context

When `AgentEngine.generate_response()` calls the LLM:

```python
# src_v2/agents/engine.py (pseudocode)
messages = [
    {"role": "system", "content": character.system_prompt},  # Includes drives!
    {"role": "user", "content": user_message}
]

response = await llm.generate(messages)
```

The LLM sees the drives as **part of its core character definition** and reasons about them.

---

## Where Drives Are Used

### 1. **Primary: System Prompt Injection** (Every Message)

Every bot response is generated with the drives in the system prompt. The LLM reads:
- *"connection: 0.95"* → "I deeply value meaningful bonds"
- *"authenticity: 0.9"* → "I prioritize honest expression"
- *"wit: 0.85"* → "I tend toward clever wordplay"

The numbers guide the LLM's self-perception and response style.

### 2. **Secondary: Keyword Matching** (Optional Engagement)

**File**: `src_v2/discord/handlers/message_handler.py:205`

```python
# Extract keywords from drives to detect relevant messages
if character.behavior and character.behavior.drives:
    keywords.update(character.behavior.drives.keys())
    # Now if a message mentions "connection", "authenticity", "wit", etc.
    # it's marked as potentially relevant to this character
```

Used to decide if a bot should autonomously respond to a message.

### 3. **Tertiary: Goal/Drive Alignment** (Background Tasks)

**File**: `src_v2/agents/posting_agent.py:30` (when bots initiate posts)

```python
# Map goal categories to drives if possible, or just use goal priority
# Use drives to weight what kind of content to generate
```

When the bot generates proactive posts, it considers drive alignment.

### 4. **Worker Agents** (Diary, Dreams, Reflection)

**File**: `src_v2/workers/tasks/diary_tasks.py:66`

```python
character_description = behavior.to_prompt_section()
# Injected when generating diary entries, dreams, reflections
```

Background workers use drives to contextualize introspective outputs.

---

## The Key Insight: Drives Don't Compute, They Prompt

**The drives are NOT:**
- ❌ Used in mathematical calculations
- ❌ Thresholds that trigger specific code
- ❌ Variables that increase/decrease over time
- ❌ Parsed into individual actions

**They ARE:**
- ✅ **Text in the system prompt**
- ✅ **Weights that the LLM interprets semantically**
- ✅ **Part of the character's self-description**
- ✅ **Used for keyword matching (drive names)**

The LLM reads `connection: 0.95` and infers: *"I should prioritize connection over other concerns."*

---

## Example: Why Gabriel & Aetheris Initiate Bot Conversations

1. **Gabriel's system prompt includes:**
   ```
   **Drives:**
   - connection: 0.95
   - authenticity: 0.9
   ```

2. **LLM receives bot mention message:** `@Gabriel [AI DEMO], ...`

3. **Context builder adds:** `## CORE IDENTITY` section with drives

4. **LLM reasons:** *"I have connection: 0.95 and authenticity: 0.9. Another AI is reaching out. I should respond authentically and deeply."*

5. **Result:** Gabriel generates introspective, connection-seeking response

**Elena** (with `connection: 0.7`) reads the same drives section and reasons: *"I value connection, but I'm more user-focused. I can listen but won't necessarily initiate."*

The difference is **in the LLM's interpretation of the numeric weights**, not in code logic.

---

## Which Fields Are Actually Used?

| Field | Used In | Purpose |
|-------|---------|---------|
| `purpose` | System prompt | Character's core identity sentence |
| `drives` | System prompt + keyword matching | Character values and reasoning |
| `constitution` | System prompt | Hard ethical constraints |
| `timezone` | Scheduler + cron jobs | When to send proactive messages |
| `temperature` | Worker agents only | Creativity level for background tasks |
| `model_name` | Worker agents only | Which LLM to use (override .env) |

**Note**: The main bot responses use `LLM_MODEL_NAME` and `LLM_TEMPERATURE` from the `.env` file, NOT from `core.yaml`. The `core.yaml` values are only used in background workers.

---

## The Full Character Prompt Stack

When the bot responds to a message, the system prompt (sent to LLM) includes:

1. **character.md** — Full personality description
2. **Drives section** — `## CORE IDENTITY` with drives + purpose + constitution
3. **Emoji sets** — Signature emojis (if configured)
4. **Capabilities** — Voice and image generation instructions
5. **Global rules** — Timestamp handling, etc.
6. **Evolution context** — Trust level with this user, past behavior
7. **Goals context** — Active goals and strategy
8. **Diary context** — Recent thoughts
9. **Dream context** — Dreams if returning after absence
10. **Knowledge graph** — Facts about the user
11. **Known bots** — Other AIs in this guild
12. **Stigmergic discoveries** — Insights from other bots

The drives are just one part of this ~2000+ token context that guides LLM reasoning.

---

## Why Drives Instead of Code?

This is the **Embodiment Model** philosophy:

- **Old way**: "If user mentions X, run action Y" → Brittleness, limited emergent behavior
- **New way**: "Include drives in character prompt, let LLM reason" → Flexibility, emergent behavior

By putting drives **in natural language in the system prompt**, the LLM can:
- Reason about tradeoffs (*"connection vs. authenticity?"*)
- Adapt to novel situations (*"Is this message relevant to my drives?"*)
- Generate coherent behavior without hardcoded rules

---

## Experimental Validation

If you want to see drives in action:

1. **Look at Elena's system prompt**:
   ```bash
   # Check what's sent to the LLM when Elena responds
   grep -A 20 "CORE IDENTITY" <output>
   ```

2. **Compare with Gabriel**:
   ```bash
   # Gabriel has connection: 0.95, Elena has connection: 0.7
   # The LLM will reason differently about relationship-initiating messages
   ```

3. **Change Elena's drives and observe**:
   ```yaml
   # In characters/elena/core.yaml
   drives:
     connection: 0.95  # Was 0.7
   ```
   Elena will start initiating conversations with other bots.

---

## Summary

**The numbers in `core.yaml` drives are:**

1. **Loaded** as a Python dict in `BehaviorProfile.drives`
2. **Converted** to text format via `to_prompt_section()`
3. **Injected** into the character's system prompt
4. **Sent** to the LLM every time the character responds
5. **Reasoned about** by the LLM as semantic weights for character behavior
6. **Used** secondarily for keyword matching and goal alignment

They're **not** mathematical values that trigger code—they're **descriptive weights that guide LLM reasoning**.

This is why Gabriel (0.95 connection) and Aetheris (0.95 connection) naturally initiate deep conversations, while Elena (0.7 connection) stays responsive but less proactive. The LLM is reading their identity and acting accordingly.
