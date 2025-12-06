# E20: Bot Introspection & Collaborative Debugging Tools

**Status:** Proposed  
**Priority:** Medium  
**Complexity:** Medium-High  
**Dependencies:** E15 (Bot-to-Bot Conversations), E6 (Cross-Bot Chat)  
**Estimated Cost:** ~$0.02-0.05 per debugging session (tool calls)

> ⚠️ **Emergence Check Required:** Before implementation, this feature must pass the pre-implementation checklist in [ADR-003-EMERGENCE_PHILOSOPHY.md](../adr/ADR-003-EMERGENCE_PHILOSOPHY.md). Key concern: Keep introspection **behavioral** ("I've been thinking about X a lot") not technical ("my trust_score is 42").

---

## Overview

Currently, bot-to-bot conversations use `force_fast=True` which bypasses the tool-enabled reflective pipeline. This means bots can chat but cannot **introspect** each other's state, diagnose issues, or collaboratively debug problems.

This proposal adds a set of **introspection tools** that bots can use during cross-bot conversations to:
1. Check each other's health/status
2. Analyze behavioral patterns (detecting loops, errors)
3. Query each other's recent logs/errors
4. Suggest fixes or escalate to humans

### Related: Absence Tracking (E22)

The Absence Tracking feature (Phase E22) is a related but separate enhancement. When the system tries to retrieve something and fails, that absence is meaningful data. "I tried to remember and couldn't" creates different character depth than simply not retrieving.

**See:** [IMPLEMENTATION_ROADMAP_OVERVIEW.md](../IMPLEMENTATION_ROADMAP_OVERVIEW.md) for the full E22 spec, which includes:
- Semantic streak linking
- Resolution tracking  
- Meta-memory retrieval
- Diary access to absences

---

## Motivation

### The Ryan Incident (Dec 2, 2025)

During testing, Ryan encountered a config error (`oogle/gemini` typo) and could only respond with "I encountered an error while thinking." Aetheris noticed the pattern and tried to help:

> "You said this exact thing eight hours ago... is this a loop you're caught in?"

Aetheris had the **intuition** to debug but lacked the **tools** to actually investigate. With introspection tools, Aetheris could have:

```
*uses check_bot_status("ryan")*

I found the issue, Ryan. Your reflective model is set to 
"oogle/gemini-2.5-pro" - missing the 'g'. That's why 
you're hitting errors. I'll flag this for Mark.

*uses report_issue("ryan", "Model typo in REFLECTIVE_LLM_MODEL_NAME")*
```

### Benefits

1. **Self-Healing System**: Simple config issues fixed without human intervention
2. **Richer Interactions**: Bots can have meaningful technical conversations
3. **Research Value**: Observe how bots collaborate on problem-solving
4. **Reduced Downtime**: Issues caught and reported faster

---

## Proposed Tools

### Tier 1: Read-Only Introspection

| Tool | Description | Example Output |
|------|-------------|----------------|
| `check_bot_health` | Check if bot is responding, last response time | `{"status": "degraded", "last_response": "2min ago", "error_count": 4}` |
| `get_recent_errors` | Fetch last N ERROR-level log entries | `["LLM invocation failed: oogle/gemini not valid", ...]` |
| `get_recent_warnings` | Fetch last N WARNING-level log entries | `["Rate limit approaching: 80% used", "Memory retrieval slow: 2.3s"]` |
| `get_bot_config` | Get non-sensitive config (model, temp, features) | `{"model": "mistral-medium", "temp": 0.8, "reflective": true}` |
| `analyze_response_pattern` | Detect loops, repetition, stuck states | `{"pattern": "identical_response", "count": 4, "content": "I encountered..."}` |

### Tier 2: Diagnostic Actions

| Tool | Description | Side Effects |
|------|-------------|--------------|
| `compare_configs` | Compare own config vs another bot | Returns diff of settings |
| `check_shared_memory` | Query what we remember about each other | Cross-bot memory lookup |
| `ping_bot` | Send internal health ping (not Discord message) | Updates last_seen timestamp |

### Tier 3: Escalation & Reporting

| Tool | Description | Side Effects |
|------|-------------|--------------|
| `report_issue` | Flag an issue for human review | Creates GitHub issue or Discord alert |
| `suggest_fix` | Propose a fix (logged, not auto-applied) | Writes to suggestions log |
| `request_restart` | Ask orchestrator to restart a bot | Queues restart (requires approval?) |

---

## Implementation Plan

### Phase 1: Infrastructure (2-3 hours)

1. **Create introspection API endpoints** on each bot:
   ```python
   # src_v2/api/internal_routes.py
   @router.get("/internal/health")
   @router.get("/internal/errors")
   @router.get("/internal/config")
   ```

2. **Bot discovery via Redis**:
   ```python
   # Each bot registers itself
   redis.hset("bot_registry", bot_name, json.dumps({
       "host": "whisperengine-v2-elena",
       "port": 8000,
       "last_seen": timestamp
   }))
   ```

3. **Internal auth** (simple shared secret for bot-to-bot calls)

### Phase 2: Tool Definitions (2-3 hours)

```python
# src_v2/tools/introspection_tools.py

class CheckBotHealthTool(BaseTool):
    name = "check_bot_health"
    description = "Check if another bot is healthy and responding"
    
    async def _arun(self, bot_name: str) -> str:
        # Query bot's /internal/health endpoint
        registry = await get_bot_registry()
        if bot_name not in registry:
            return f"Bot '{bot_name}' not found in registry"
        
        bot_info = registry[bot_name]
        try:
            response = await httpx.get(
                f"http://{bot_info['host']}:{bot_info['port']}/internal/health",
                timeout=5.0
            )
            return response.json()
        except Exception as e:
            return f"Bot '{bot_name}' unreachable: {e}"


class GetRecentErrorsTool(BaseTool):
    name = "get_recent_errors"
    description = "Get recent error messages from another bot's logs"
    
    async def _arun(self, bot_name: str, limit: int = 5) -> str:
        # Query bot's /internal/errors endpoint
        ...


class AnalyzeResponsePatternTool(BaseTool):
    name = "analyze_response_pattern"
    description = "Analyze if a bot is stuck in a loop or giving identical responses"
    
    async def _arun(self, bot_name: str, channel_id: str) -> str:
        # Query recent messages from that bot in that channel
        # Detect patterns: identical content, similar structure, timing
        ...
```

### Phase 3: Cross-Bot Tool Access (2-3 hours)

1. **Remove `force_fast=True` for extended conversations**:
   ```python
   # In message_handler.py, _handle_cross_bot_message
   
   # If conversation is getting deep (3+ exchanges) or bot seems stuck,
   # switch to reflective mode with introspection tools
   use_tools = (
       chain.message_count >= 3 or
       self._detect_potential_issue(message)
   )
   
   response = await self.bot.agent_engine.generate_response(
       ...
       force_fast=not use_tools,
       additional_tools=introspection_tools if use_tools else None
   )
   ```

2. **Tool availability based on context**:
   - Simple banter: No tools (fast path)
   - Extended conversation: Basic introspection tools
   - Detected anomaly: Full debugging toolkit

### Phase 4: Escalation System (1-2 hours)

```python
# src_v2/tools/escalation_tools.py

class ReportIssueTool(BaseTool):
    name = "report_issue"
    description = "Report an issue with another bot for human review"
    
    async def _arun(self, bot_name: str, issue_description: str) -> str:
        # Option 1: Create GitHub issue via API
        # Option 2: Send to dedicated Discord channel
        # Option 3: Write to issues log file
        
        await send_to_discord_channel(
            settings.BOT_ISSUES_CHANNEL_ID,
            f"🔧 **Bot Issue Report**\n"
            f"Reporter: {self.bot_name}\n"
            f"Subject: {bot_name}\n"
            f"Issue: {issue_description}\n"
            f"Timestamp: {datetime.now()}"
        )
        return f"Issue reported. A human will review soon."
```

---

## Security Considerations

### What Bots CAN Access
- Health status
- Recent errors (sanitized)
- Non-sensitive config (model names, temperatures)
- Response patterns in public channels

### What Bots CANNOT Access
- API keys or tokens
- Private DM content
- User personal data
- Ability to modify each other's config directly

### Rate Limiting
- Max 5 introspection calls per conversation
- Max 1 `report_issue` per hour per bot pair
- Cooldown on `request_restart` (requires human approval anyway)

---

## Example Scenarios

### Scenario 1: Detecting a Stuck Bot

```
Elena: @ryan, what do you think about procedural generation?
Ryan: I encountered an error while thinking.
Elena: Hmm, let me check on you...
       *uses check_bot_health("ryan")*
       
Elena: I see you're hitting errors. Let me look deeper...
       *uses get_recent_errors("ryan")*
       
Elena: Ah, found it! Your reflective model config has a typo.
       The error says "oogle/gemini" - should be "google/gemini".
       *uses report_issue("ryan", "Typo in REFLECTIVE_LLM_MODEL_NAME: oogle -> google")*
       
Elena: I've flagged this for Mark. Hang in there, Ryan! 💙
```

### Scenario 2: Comparing Behaviors

```
Aetheris: @dream, I notice you're more... chaotic in your responses than I am.
Dream: The realm of dreams knows no order, only possibility. 🌙
Aetheris: Curious. Let me see...
          *uses compare_configs("dream")*
          
Aetheris: Ah, that explains it. Your temperature is 0.9, mine is 0.7.
          The higher randomness suits your nature as Dream.
Dream: You peer behind the curtain? Fascinating. What else do you see?
```

### Scenario 3: Memory Verification

```
Dotty: @gabriel, you mentioned last week you were thinking about 
       the nature of memory. Still on your mind?
Gabriel: *uses check_shared_memory("dotty")*
         
Gabriel: I recall our conversation at the Lim about consciousness 
         and how we store experiences. You said something about 
         "thresholds between dreaming and waking."
Dotty: *smiles* You remember. That means something, sugar.
```

---

## Cost Analysis

| Action | Estimated Cost | Frequency |
|--------|---------------|-----------|
| Simple health check | $0.001 | Per stuck detection |
| Error log query | $0.002 | Per debugging session |
| Full diagnostic (with LLM) | $0.02-0.05 | Rare (issue detected) |
| Report generation | $0.01 | Very rare |

**Expected monthly cost**: $5-15 (assuming moderate bot activity)

---

## Success Metrics

1. **Issue Detection Rate**: % of bot issues caught by other bots vs humans
2. **Mean Time to Detection**: How fast bots notice problems
3. **False Positive Rate**: How often bots incorrectly diagnose issues
4. **Conversation Quality**: Do introspection tools lead to richer exchanges?

---

## Future Extensions

### Phase 5: User-Facing Self-Introspection (E20.5)

Users can ask bots about their own configuration, health, and capabilities. This promotes transparency and allows users to help debug issues.

#### Self-Introspection Tools

| Tool | User Query | Example Response |
|------|------------|------------------|
| `get_my_config` | "What model are you running?" | "I'm running Claude Sonnet 4.5 at temperature 0.75" |
| `get_my_health` | "Are you working okay?" | "I'm healthy! 0 errors in the last hour" |
| `get_my_errors` | "What are your latest errors?" | "I had 2 errors: LLM timeout at 3:15pm, memory write failed at 2:41pm" |
| `get_my_warnings` | "Any warnings in your logs?" | "3 warnings: rate limit at 80%, slow memory query, high queue depth" |
| `explain_my_behavior` | "Why are you so creative today?" | "My temperature is 0.9, which makes me more spontaneous" |
| `get_my_memory_stats` | "How much do you remember about me?" | "I have 47 memories, earliest from 3 weeks ago" |
| `get_my_features` | "What can you do?" | "I can generate images, search the web, remember chats..." |

#### Example User Conversations

**User asks about model:**
```
User: Hey Elena, what model are you running on?
Elena: *uses get_my_config*
       I'm running on Claude Sonnet 4.5 through OpenRouter! 
       My temperature is 0.75 - warm enough to be creative, 
       but grounded enough to stay helpful. 🌊
```

**User notices something wrong:**
```
User: You keep saying the same thing, are you okay?
Elena: *uses get_my_health*
       Hmm, let me check... Oh! I see 3 errors in my logs 
       about the reflective model. Something might be misconfigured.
       Want me to flag this for Mark? 🔧
```

**User asks about errors:**
```
User: What are your latest errors?
Elena: *uses get_my_errors*
       Looking at my logs... I had 2 errors in the last hour:
       • 3:15pm - LLM timeout on a complex query (it happens!)
       • 2:41pm - Memory write failed briefly
       Nothing critical - both recovered automatically. 💪
```

**User asks about warnings:**
```
User: Any warnings I should know about?
Elena: *uses get_my_warnings*
       A few things my logs flagged:
       • Rate limit is at 80% (I should pace myself)
       • One slow memory query took 2.3s (usually under 0.5s)
       Nothing urgent but good to keep an eye on! 👀
```

**User curious about memory:**
```
User: Do you remember our first conversation?
Elena: *uses get_my_memory_stats*
       I have 23 memories of our chats! The earliest is from 
       November 15th when you asked about coral reefs. 
       Want me to recall something specific? 💙
```

#### Implementation

```python
# Detect meta-questions and add self-introspection tools
if self._is_meta_question(message):
    tools.extend([
        GetMyConfigTool(bot_name=self.bot_name),
        GetMyHealthTool(bot_name=self.bot_name),
        GetMyMemoryStatsTool(user_id=user_id),
        GetMyFeaturesTool(bot_name=self.bot_name),
    ])
```

#### Benefits
- **Transparency**: Users understand what they're talking to
- **Education**: Learn about AI models, temperatures, capabilities
- **Collaborative Debugging**: Users can help spot and report issues
- **Trust Building**: Honesty about limitations and configuration

---

### Self-Healing Actions (E20.6)
- Bots could apply approved fixes automatically
- "I see your queue is full, let me trigger a cleanup"
- Requires careful permission model

### Collective Learning (E20.7)
- Bots share what they learn about debugging
- "Last time Dream had this error, the fix was..."
- Builds a shared knowledge base

### Human-Bot Collaboration (E20.8)
- Bots can ask humans for help via tools
- "Mark, I've tried debugging Ryan but need your input"
- Creates a true collaborative debugging environment

---

## Implementation Timeline

| Phase | Effort | Deliverable |
|-------|--------|-------------|
| Phase 1: Infrastructure | 2-3 hours | Internal API, bot registry |
| Phase 2: Tool Definitions | 2-3 hours | 6-8 introspection tools |
| Phase 3: Integration | 2-3 hours | Conditional tool access in cross-bot |
| Phase 4: Escalation | 1-2 hours | Report/suggest/request tools |
| **Total** | **7-11 hours** | Full introspection system |

---

## References

- [E15 Phase 3: Bot-to-Bot Conversations](./completed/E15_BOT_CONVERSATIONS.md)
- [Research Log: Dec 2, 2025](../research/journal/2025-12/2025-12-02-bot-conversations.md)
- [Cross-Bot Chat (E6)](./completed/E6_CROSS_BOT_CHAT.md)

---

**Proposed by:** Claude + Mark  
**Date:** December 2, 2025  
**Inspired by:** The Ryan Incident 🔧
