# Stats Footer Feature

The Stats Footer is a toggleable feature that displays detailed engagement metrics at the bottom of Discord bot responses. It provides transparency into relationship progression, memory usage, and system performance.

## 📊 What's Displayed

The footer shows:

### 💙 Relationship Metrics
- **Trust Score**: Current trust level (0-150)
- **Relationship Level**: Stranger → Acquaintance → Friend → Close Friend → Confidant
- **Unlocked Traits**: Special personality traits revealed through relationship depth
- **Interaction Count**: Total number of conversations

### 🎯 Active Goals
- Shows up to 2 active learning/relationship goals the character is working toward
- Based on the goals system in `characters/{name}/goals.yaml`

### 🧠 Memory Context
- Number of relevant memories retrieved from vector database
- Provides insight into how much context the bot used for the response

### 💡 Latest Insight
- Most recent reflection or learning from the character's self-reflection system
- Shows what the character has recently "realized" about the user

### ⚡ Performance Metrics
- **Total Time**: Complete response generation time
- **LLM Time**: Time spent in language model processing
- **Overhead**: Database queries, memory retrieval, etc.

## 🎮 Usage

### For Users

Enable the footer for your account:
```
/elena stats_footer enable
```

Disable it:
```
/elena stats_footer disable
```

### For Developers

The footer is implemented in `src_v2/utils/stats_footer.py` and integrated into the Discord bot message flow.

#### Programmatic Access

```python
from src_v2.utils.stats_footer import stats_footer

# Check if enabled for user
is_enabled = await stats_footer.is_enabled_for_user(user_id, character_name)

# Generate full footer
footer = await stats_footer.generate_footer(
    user_id=user_id,
    character_name=character_name,
    memory_count=15,
    processing_time_ms=2543,
    llm_time_ms=1284,
    response_length=450
)

# Generate compact footer (one line)
compact = await stats_footer.generate_compact_footer(
    user_id=user_id,
    character_name=character_name,
    memory_count=15,
    processing_time_ms=2543
)
```

## 🔧 Configuration

Footer visibility is stored in user preferences:

```python
# Enable for specific user
await trust_manager.update_preference(user_id, character_name, "show_stats_footer", True)

# Disable for specific user
await trust_manager.update_preference(user_id, character_name, "show_stats_footer", False)
```

## 📝 Example Output

```
──────────────────────────────────────────────────
💙 **Relationship**: Close Friend (Trust: 91/150 [empathetic, playful]) • 68 interactions
🎯 **Active Goals**: Build Trust, Share Stories
🧠 **Memory**: Retrieved 15 relevant memories
💡 **Recent Insight**: User values emotional support and optimism
⚡ **Performance**: Total: 2543ms | LLM: 1284ms | Overhead: 1259ms
──────────────────────────────────────────────────
```

## 🎯 Design Philosophy

### Why Optional?
Some users prefer minimal, clean responses. Others love seeing "under the hood" metrics. Making it toggleable respects both preferences.

### Transparency
The footer demystifies AI interactions by showing:
- What data the bot used (memory count)
- How the relationship is progressing (trust, traits)
- System performance (is the bot slow today?)

### Engagement
Users are more likely to engage when they see tangible progress (trust score going up, traits unlocking, goals advancing).

## 🧪 Testing

Run the test script:
```bash
source .venv/bin/activate
python tests_v2/test_stats_footer.py
```

This will:
1. Enable the footer for a test user
2. Generate a full footer with sample data
3. Generate a compact footer
4. Disable the footer

## 🚀 Integration Points

The footer is integrated at:
- **Discord Bot**: `src_v2/discord/bot.py` - Appends footer after response generation
- **Commands**: `src_v2/discord/commands.py` - `/stats_footer` toggle command
- **Preferences**: Stored in `v2_user_relationships.preferences` JSONB field

## 🔮 Future Enhancements

Potential additions:
- **Emotion Detection**: Show detected user emotion from message
- **Conversation Depth**: Indicate how deep/meaningful the current conversation is
- **Learning Progress**: Show progress on specific skill/knowledge acquisition
- **Cost Tracking**: Display estimated API cost for power users
- **Comparison Stats**: "You're more active than 75% of users"

## 🐛 Troubleshooting

**Footer not showing?**
1. Check if enabled: `/elena stats_footer`
2. Verify database connection
3. Check logs for errors in `logs/`

**Wrong stats displayed?**
1. Trust score might be cached - it updates after each interaction
2. Interaction count is based on stored messages in `v2_chat_history`

**Performance impact?**
Minimal - footer generation adds ~50-100ms overhead due to database queries.
