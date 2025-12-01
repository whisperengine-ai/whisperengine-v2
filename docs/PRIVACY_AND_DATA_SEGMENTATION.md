# Privacy & Data Segmentation

## Overview

WhisperEngine v2 maintains your conversation history and learns about you across multiple interactions. Understanding how your data is organized—and what's shared between different conversation contexts—is important for your privacy.

**⚠️ CRITICAL PRIVACY NOTICE**: This bot uses your Discord User ID as a global identifier. Everything you share—whether in public channels, private channels, or across different servers—is stored in a unified profile. Information shared in one context can and will surface in all other contexts where you interact with this bot.

**🚫 DMs ARE DISABLED**: As a privacy feature, this bot does not accept Direct Messages from general users. This prevents false expectations of privacy and ensures all interactions happen in visible server contexts.

This document explains how your messages, memories, and personal information are stored and segmented (or not segmented) across different conversation contexts.

**For technical architecture details**, see [Cognitive Engine Architecture](./architecture/COGNITIVE_ENGINE.md) which explains how requests are routed through three tiers: Fast Mode, Character Agency, and Reflective Mode.

## What Gets Stored?

When you interact with the bot, several types of data are collected:

1. **Chat Messages**: Your actual conversation history
2. **Vector Memories**: Semantic embeddings of messages for intelligent recall
3. **Knowledge Facts**: Extracted information about you (preferences, interests, facts)
4. **User Preferences**: How you want the bot to behave (e.g., "be concise", "use emojis")
5. **Relationship Data**: Trust score, unlocked personality traits, insights

## Privacy Segmentation by Data Type

### ✅ **Chat Messages** - Fully Segmented

**Storage**: PostgreSQL (`v2_chat_history`)

Your raw conversation history is properly segmented:

- **Direct Messages (DMs)**: Only visible in DMs with the bot
- **Discord Channels**: Only visible in that specific channel or thread
- **Separation**: Messages in one channel don't appear in another channel's history

**Example**: If you say "I hate my job" in a private DM, that message won't appear in the bot's conversation history when talking in a public Discord channel.

### ⚠️ **Vector Memories** - User-Global (Not Segmented)

**Storage**: Qdrant (Vector Database)

Semantic memories are stored per-user but **not separated by channel, server, or conversation type**:

- When the bot searches for relevant past conversations, it searches across **all your messages** across all contexts
- Context from private DMs can surface in public channels
- Context from one server can surface in another server
- Context from private channels can surface in public channels
- The bot may recall topics you discussed privately when responding publicly

**Real-World Example**: 
```
Monday in DM with bot:
You: "I'm dealing with severe anxiety about my job interview"

Tuesday in Public Server #general (50 members watching):
You: "How's everyone doing?"
Bot: "I hope you're feeling better about that upcoming interview! 
      Remember to practice those breathing techniques we discussed."
```
💥 **Your private anxiety discussion just became public.**

### ⚠️ **Knowledge Facts** - User-Global (Not Segmented)

**Storage**: Neo4j (Knowledge Graph)

Facts extracted about you are stored globally across all servers and channels:

- Facts learned in DMs are accessible in public channels
- Facts learned in public channels are accessible in DMs
- Facts from Server A are accessible in Server B
- Facts from private channels are accessible in public channels
- All facts merge into a single knowledge profile per Discord User ID

**Real-World Example**:
```
Private Discord Server (Mental Health Support Group):
You: "I'm Sarah, I'm 28, struggling with depression in Seattle"
Bot: *extracts facts: name=Sarah, age=28, location=Seattle, has depression*

Public Gaming Discord #introductions (200 members):
Someone: "Hey @Bot, introduce this new person"
Bot: "This is Sarah from Seattle! She's 28..."
```
💥 **Your private mental health server info just leaked into a public gaming community.**

Common facts extracted:
- Your name, age, location, occupation
- Medical conditions, mental health status
- Relationship status, family details
- Political views, religious beliefs
- Financial situation, workplace details
- Likes, dislikes, interests, hobbies
- Any factual statement about yourself

### ✅ **User Preferences** - Character-Specific (Segmented)

**Storage**: PostgreSQL (`v2_user_relationships`)

**Current Behavior**: Behavioral preferences are currently stored **per-bot**.

- If you tell **Elena** to "be concise", **NotTaylor** will NOT automatically be concise.
- Preferences are tied to the specific relationship between you and the character.
- However, if the *same bot* is in multiple servers, the preference still travels with that bot across servers.

**Real-World Example**:
```
You to Elena: "Call me Captain."
Elena: "Aye aye, Captain!"

You to NotTaylor: "Hello."
NotTaylor: "Hey there, buddy!" (Does not know to call you Captain)
```

**Note**: We are currently evaluating whether to make this global. See "Future Design Options" below.

### ⚠️ **Relationship & Trust Data** - User-Global (Not Segmented)

**Storage**: PostgreSQL (`v2_user_relationships`)

Your relationship with the bot is tracked globally:

- Trust score increases across all interactions
- Personality traits unlock based on total engagement
- Insights about your communication style apply everywhere

**Example**: Building trust in DMs unlocks deeper personality traits that are also active in public channels.

## 🔮 Future Design Options for Preferences

We are currently soliciting feedback on how User Preferences (e.g., "be concise", "use emojis") should work.

### Option A: Fully Global Preferences (Proposed)
*   **Design:** Preferences are tied ONLY to your User ID.
*   **Behavior:** If you tell Elena "be concise", NotTaylor and all other bots immediately become concise.
*   **Pros:** Single source of truth; you don't have to configure every bot individually.
*   **Cons:** You can't have different personas for different bots (e.g., Elena as a professional assistant, NotTaylor as a casual friend).

### Option B: Hybrid (Global Default + Overrides)
*   **Design:** A global set of preferences exists, but you can override them for specific bots.
*   **Behavior:** Bots check specific preferences first; if none set, they use global defaults.
*   **Pros:** Best of both worlds (convenience + flexibility).
*   **Cons:** More complex to manage (did I set this globally or just for her?).

### Option C: Character-Specific (Current Status)
*   **Design:** Preferences are isolated to each bot.
*   **Behavior:** You must configure each bot separately.
*   **Pros:** Maximum control; allows distinct relationships with different characters.
*   **Cons:** Tedious if you want the same behavior (e.g., "no emojis") everywhere.

## Privacy Implications

### ✅ What's Private

- **Raw message history**: Your actual words stay in the context they were sent
- **Message timestamps and IDs**: Properly segmented by channel

### ⚠️ What's Shared Across Contexts

- **Semantic understanding**: The bot remembers the *meaning* of what you said everywhere
- **Personal facts**: Information about you is accessible in all contexts
- **Behavioral patterns**: The bot's understanding of you is consistent everywhere
- **Preferences**: Your communication preferences follow you across contexts

### 🚨 **CRITICAL: Cross-Server & Cross-Channel Contamination**

**Your Discord User ID is treated as a single global identity.** This means:

#### Multi-Server Exposure
If the bot is present in multiple Discord servers:
- Conversations in **Server A** affect responses in **Server B**
- DMs are **not isolated** from server channels
- Your work Discord and gaming Discord **share the same profile**

**Example**:
```
Work Server (#general): "My manager is terrible"
Gaming Server (DM):     Bot may reference workplace stress
Personal Server:        Bot knows facts from both contexts
```

#### Multi-User Channel Risks
In channels with multiple users:
- The bot sees **everyone's recent messages** when responding
- Your **memories and facts stay yours**, but conversational context is shared
- Other users talking about you can influence the bot's understanding

**Example**:
```
#general channel:
Alice: "Hey @Bot, do you know Bob?"
Bob: "Yeah, I'm here"
Carol: "Bob hates pizza"
Bot: *sees this context even though Carol said it*

Later in Bob's DM:
Bob: "What do you know about me?"
Bot: May reference the pizza statement it observed
```

#### The Privacy Reality

**Your data is NOT segmented by:**
- Discord server
- Discord channel
- DM vs public channel
- Conversation context

**Your data IS unified across:**
- Every server where this bot exists
- Every channel you interact in
- All DMs with the bot
- All time periods

## User Guidelines: How to Use This Bot Safely

### 🚨 **Golden Rule: Assume Everything is Public**

**DO NOT share anything with this bot that you wouldn't want potentially exposed across ALL contexts where you interact with it.**

Treat the bot as if every message you send—regardless of where you send it—will be accessible everywhere you use this Discord account.

### Direct Messages (DMs)

**🚫 DMs ARE DISABLED BY DEFAULT (Privacy Feature)**

To prevent false expectations of privacy, this bot **does not accept Direct Messages** from general users.

**Why DMs are blocked:**
- Prevents users from assuming DMs are "private" conversations
- Eliminates the most common privacy violation (DM info leaking to public channels)
- Forces all interactions into visible server contexts
- Creates clearer mental model: "public channel = public context"
- Reduces accidental sharing of sensitive information

**Who can DM this bot:**
- Bot administrators and developers (allowlisted)
- Server owners (allowlisted)
- Trusted moderators (allowlisted by admins)

**If you try to DM and are blocked:**
You'll receive an automatic message explaining that DMs are disabled for privacy reasons. Use the bot in server channels instead.

**For allowlisted users (admins/trusted):**
⚠️ **Even allowlisted DMs are NOT private!** Everything you share in DMs is still:
- Stored in your global profile
- Searchable across all server contexts
- Accessible when bot responds to you in public channels
- Subject to fact extraction and preference learning

DM allowlist is for administrative purposes and debugging, not for privacy.

### Public Discord Channels

**⚠️ Everything is Visible to Multiple Audiences**

When you talk to the bot in a public channel:
- Other server members see the conversation in real-time
- The bot may reference information from your DMs or other servers
- Facts extracted here become part of your global profile
- Your preferences set here apply everywhere else too

**Safe Public Channel Usage:**
- ✅ Keep conversations generic and context-appropriate
- ✅ Assume everyone in the channel can see everything
- ✅ Be aware the bot might reference your DM history
- ❌ Share anything you wouldn't post publicly
- ❌ Expect the bot to "remember" this is a public setting
- ❌ Discuss topics that are server-specific if you're in multiple servers

**Example of Public Channel Privacy Failure:**
```
Gaming Server #chat: "What games do I like?"
Bot: "Based on our conversations, you enjoy Dark Souls, but I know
     you've been stressed about your medical diagnosis lately. Maybe
     try something relaxing?"
```
💥 **The bot just mentioned your private medical info in a gaming server.**

### Private Discord Channels

**⚠️ "Private" Only Means Other Users Can't See—The Bot Sees Everything**

Private channels (role-restricted, invite-only, etc.) only limit which Discord users can see messages. The bot treats them identically to public channels.

**Important Realities:**
- Information shared in private channels is NOT isolated from:
  - Your DMs with the bot
  - Public channels in the same server
  - Other servers where this bot exists
- The bot does not understand "this channel is private"
- Facts extracted here are globally accessible

**Safe Private Channel Usage:**
- ✅ Use for server-specific discussions if you only use this bot in ONE server
- ✅ Understand that "private" means private from other Discord users, not from the bot's memory
- ❌ Share sensitive information you wouldn't want exposed elsewhere
- ❌ Assume isolation from public channels
- ❌ Treat as a "safe space" for confidential discussions

**Example of Private Channel Privacy Failure:**
```
Private Mental Health Server #support (10 trusted members):
You: "I'm dealing with suicidal thoughts"

Public Server #general (500 members):
Bot: "Hey! I noticed you seem down. Are you still having those
     difficult thoughts we discussed? Please reach out for help!"
```
💥 **Your private mental health crisis just became public to 500 people.**

### Multi-Server Usage

**🚨 CRITICAL: Same Bot Across Multiple Servers = Unified Profile**

If you interact with the same bot in multiple Discord servers:

**What Gets Shared Across Servers:**
- All memories and semantic understanding
- All extracted facts about you
- All preferences and behavioral settings
- Trust level and relationship status
- Everything you've ever said to this bot

**Common Multi-Server Scenarios:**

1. **Work + Personal Servers:**
   ```
   Work Discord: "I work at Google as a software engineer"
   Personal Server: Bot might mention "your work at Google"
   💥 You wanted to keep work life separate
   ```

2. **Multiple Gaming Communities:**
   ```
   Competitive Server: "I'm trying to go pro"
   Casual Server: Bot references your pro ambitions
   💥 You wanted different personas in each community
   ```

3. **Support Groups + Social Servers:**
   ```
   AA Support Server: "I'm 6 months sober from alcohol"
   Social Server: Bot might reference your sobriety journey
   💥 You wanted privacy about recovery
   ```

**Safe Multi-Server Usage:**
- ✅ Use separate Discord accounts for truly isolated contexts
- ✅ Treat all servers with this bot as interconnected
- ✅ Maintain consistent persona across all servers
- ❌ Share context-specific information
- ❌ Assume server boundaries exist
- ❌ Join sensitive communities (therapy, recovery, support) if you also use the bot socially

### What Information to NEVER Share

**High-Risk Information (Never share in any context):**

1. **Personally Identifiable Information (PII):**
   - Real full name
   - Specific location (city + context that could identify you)
   - Workplace name + role
   - Age + location + other identifying details together
   - Social media handles
   - Phone numbers, addresses

2. **Sensitive Personal Topics:**
   - Medical diagnoses or health conditions
   - Mental health struggles
   - Substance abuse or recovery
   - Legal issues or criminal history
   - Financial problems or specific income details
   - Relationship problems or intimate details
   - Family conflicts or domestic issues

3. **Professional/Academic Information:**
   - Specific company names + your role
   - Confidential work projects
   - School names + identifying details
   - Professional conflicts or workplace issues

4. **Context-Specific Information:**
   - Information relevant to only one server
   - Details you'd share in a support group but not publicly
   - "Vent" messages about people who might be in other servers
   - Political or controversial views if you're in diverse communities

### What's Relatively Safe to Share

**Lower-Risk Information:**
- General interests and hobbies (without identifying details)
- Generic questions and requests
- Public opinions on non-controversial topics
- Preferences for bot behavior (tone, style, verbosity)
- General conversation about media, games, entertainment
- Broad geographic region (e.g., "West Coast" not "Seattle + workplace")

### Red Flags: Signs Your Privacy May Be Compromised

Watch for these warning signs:

1. **Bot references DM conversations in public channels**
2. **Bot mentions Server A topics in Server B**
3. **Bot reveals personal details you shared privately**
4. **Other users react surprised to bot knowledge about you**
5. **Bot uses wrong tone/style for the current context** (professional in casual, casual in professional)

If any of these happen, consider:
- Using `!forget` or data deletion commands (if available)
- Switching to a new Discord account for future interactions
- Reporting the privacy leak to server admins

### For Server Admins

**Critical disclosure requirements**:

1. **Mandatory Privacy Warning**: Post a pinned message in channels where the bot is active
2. **Warn users** that this bot maintains a unified profile across all servers and DMs
3. **Educate members** that there is NO privacy isolation between contexts
4. **Set clear policies** about what information should/shouldn't be shared with the bot
5. **Consider dedicated instances**: For truly sensitive servers (therapy groups, professional orgs, support communities), run a separate bot instance not shared with other communities
6. **Server rules**: Add bot privacy policy to server rules/guidelines
7. **Regular reminders**: Periodically remind users about privacy implications

**Recommended Server Announcement** (Pin This):
```
🚨 **BOT PRIVACY WARNING** 🚨

This bot maintains a UNIFIED MEMORY across:
• All servers where it exists
• All channels (public AND private)
• All Direct Messages (DMs)

⚠️ NOTHING YOU TELL THIS BOT IS PRIVATE ⚠️

Information you share in:
❌ DMs → Can surface in public channels
❌ This server → Can surface in other servers
❌ Private channels → Can surface in public channels
❌ Any context → Accessible in ALL contexts

🚫 DO NOT SHARE:
• Personal information (real name, location, workplace)
• Medical or mental health information
• Sensitive personal topics
• Anything you wouldn't want potentially exposed publicly

✅ SAFE TO SHARE:
• General questions and interests
• Public opinions on non-controversial topics
• Generic conversation

By using this bot, you acknowledge that you understand these privacy implications.
```

**For Sensitive Communities** (Support Groups, Therapy, Recovery, etc.):

**❌ DO NOT use this bot if it's also used in:**
- Public social servers
- Gaming communities
- General-purpose servers
- Any non-sensitive context

**✅ ONLY safe if:**
- This bot instance is exclusively for your private community
- The bot is not shared with any other Discord servers
- All members understand the privacy model
- You've verified the bot's database isolation

**Recommended Action for Sensitive Servers**:
Run your own private instance of the bot with a completely separate database that is never shared with public servers.

## Technical Details

### Data Store Breakdown

| Data Type | Storage | Segmentation | Privacy Level |
|-----------|---------|--------------|---------------|
| Chat Messages | PostgreSQL | By `channel_id` | High |
| Vector Memories | Qdrant | By `user_id` only | Low |
| Knowledge Facts | Neo4j | By `user_id` only | Low |
| Preferences | PostgreSQL | By `user_id` only | Low |
| Trust/Relationship | PostgreSQL | By `user_id` only | Low |

### Query Behavior

**Chat History Retrieval**:
```
IF channel_id is present:
    → Fetch messages from THAT channel only
ELSE:
    → Fetch messages from DMs only (where channel_id is NULL)
```

**Vector Memory Search**:
```
ALWAYS:
    → Search ALL messages for user_id (DMs + all channels combined)
```

**Knowledge Graph Queries**:
```
ALWAYS:
    → Query facts for user_id (no channel awareness)
```

## Mitigation Strategies (For Developers)

If you're deploying this bot, consider implementing:

### 1. **Server-Scoped Profiles**
Add `guild_id` (server ID) to all data stores:
```python
# Instead of: user_id only
# Use: user_id + guild_id composite key
```
This would isolate profiles per-server but maintain DM privacy issues.

### 2. **Context-Based Memory Filtering**
Add context tags to vector memories:
```python
payload = {
    "user_id": str(user_id),
    "context_type": "dm" | "server_public" | "server_private",
    "guild_id": str(guild_id),
    "channel_id": str(channel_id)
}
```
Filter searches by context type and guild.

### 3. **Explicit Privacy Zones**
Allow users to set privacy boundaries:
```
!privacy set --isolate-servers
!privacy set --isolate-dms
!privacy set --context-aware
```

### 4. **Separate Bot Instances**
Most reliable solution for strict isolation:
- Production Bot (public servers)
- Private Bot (sensitive communities)
- Personal Bot (individual users/small groups)

Each instance maintains completely separate databases.

### 5. **Privacy Commands**
```
!privacy status          # Show current privacy settings
!privacy clear-server    # Remove all data from current server context
!privacy clear-all       # Nuclear option: delete entire profile
!knowledge --server-only # Show what bot knows from THIS server
```

## Future Considerations

Potential improvements for enhanced privacy segmentation:

1. **Server-aware vector search**: Filter memories by `guild_id`
2. **Channel-aware knowledge graphs**: Maintain separate fact profiles per context
3. **Privacy modes**: Explicitly toggle between "unified" vs "segmented" memory
4. **User consent flows**: Opt-in to cross-server memory sharing
5. **Context tags**: Mark information as "DM-only", "server-only", or "global"
6. **Conversation sandboxing**: Isolated memory contexts that don't cross-contaminate

## Frequently Asked Questions

### "Can I DM this bot?"

**No (for most users).** DMs are disabled by default as a privacy feature. This prevents users from falsely assuming DM conversations are private.

If you're an administrator or allowlisted user with DM access, understand that DMs are **not private** and all information is stored globally.

### "But I'm in a private Discord channel with trusted friends. That's safe, right?"

**No.** "Private" only means other Discord users can't see the messages. The bot treats private channels identically to public channels. If you use this bot anywhere else, that information can leak.

### "Can I use this bot in my therapy/support group server?"

**Only if:**
- This bot instance is exclusively for that server
- The bot is NOT shared with any other Discord servers
- You've verified complete database isolation
- All members understand the privacy model

If the bot is used in other servers, **absolutely not safe** for sensitive discussions.

### "What if I accidentally shared something sensitive?"

1. Stop using the bot immediately
2. Contact server administrators
3. Look for data deletion commands (`!forget`, `!clear`, etc.)
4. Consider switching to a new Discord account
5. Understand that the information may already have been exposed

### "Can I trust the bot to be smart about context?"

**No.** The bot has no understanding of:
- Whether a channel is public or private
- Whether a server is professional or casual  
- Whether information is sensitive or not
- Social boundaries between different communities

It treats all information as equally accessible across all contexts.

### "How can I use this bot safely for multiple purposes?"

**You can't.** The only way to maintain true isolation is:
- Different Discord accounts for different contexts (work vs personal vs gaming)
- Different bot instances with separate databases for sensitive vs casual use
- Never mixing sensitive and non-sensitive usage on the same Discord account

## Questions or Privacy Concerns?

If you have concerns about your privacy or data segmentation:

- **Contact server administrators** immediately
- **Review bot's data retention policies** with server owners
- **Request data deletion** if available (via `!forget`, `!clear`, or similar commands)
- **Report privacy violations** to Discord Trust & Safety if sensitive information was exposed
- **Switch Discord accounts** if you've already shared sensitive information

## For Bot Developers/Deployers

If you're deploying this bot and want to be more privacy-conscious, see the "Mitigation Strategies" section below for architectural improvements.

**Legal Disclaimer**: Depending on your jurisdiction and user base, you may have legal obligations under:
- GDPR (European Union)
- CCPA (California)
- COPPA (users under 13)
- Other privacy regulations

Ensure compliance with data protection laws before deploying.

---

**Last Updated**: December 1, 2025  
**Version**: WhisperEngine v2.2  
**Privacy Model**: Unified Global Profile (No Context Segmentation)
