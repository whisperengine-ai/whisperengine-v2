#!/usr/bin/env python3
"""
Extract FULL Discord channel context for psychological analysis.
Pulls ALL messages from specified channels (not just target user)
to get complete picture of interactions and community dynamics.

Usage: python scripts/extract_full_channel_context.py

Target channels:
- 1373439451027734558 (ai-conversations-1)
- 1398433563162185860 (general)

Analysis period: Sept 15 - Dec 16, 2025
"""

import discord
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import os
from collections import defaultdict

# Load nottaylor bot token
env_path = Path(__file__).parent.parent / ".env.nottaylor"
load_dotenv(env_path)

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ DISCORD_TOKEN not found in .env.nottaylor")
    exit(1)

# Target user for analysis (for highlighting, but we pull ALL users)
TARGET_USER_ID = 932729340968443944

# Specific channels to extract
TARGET_CHANNELS = [
    1373439451027734558,  # ai-conversations-1
    1398433563162185860,  # general
]

# Full analysis period
START_DATE = datetime(2025, 9, 15, tzinfo=timezone.utc)
END_DATE = datetime(2025, 12, 17, tzinfo=timezone.utc)  # Include Dec 16 fully


class FullChannelExtractor(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.messages_by_channel = defaultdict(list)
        self.user_stats = defaultdict(lambda: {"messages": 0, "name": ""})
        self.bot_ids = set()
        
    async def on_ready(self):
        print(f"✓ Logged in as {self.user}")
        print(f"✓ Target channels: {TARGET_CHANNELS}")
        print(f"✓ Date range: {START_DATE.date()} to {END_DATE.date()}")
        print(f"✓ Target user for analysis: {TARGET_USER_ID}")
        print()
        
        total_messages = 0
        
        for guild in self.guilds:
            print(f"📂 Searching guild: {guild.name}")
            
            for channel in guild.text_channels:
                if channel.id not in TARGET_CHANNELS:
                    continue
                    
                try:
                    permissions = channel.permissions_for(guild.me)
                    if not permissions.read_message_history:
                        print(f"  ⚠️  No history access to {channel.name}")
                        continue
                    
                    print(f"  📝 Extracting: #{channel.name} (ID: {channel.id})")
                    
                    msg_count = 0
                    async for message in channel.history(
                        after=START_DATE,
                        before=END_DATE,
                        limit=None,
                        oldest_first=True
                    ):
                        # Track all messages from all users
                        msg_data = {
                            "timestamp": message.created_at.isoformat(),
                            "channel_id": channel.id,
                            "channel_name": channel.name,
                            "guild": guild.name,
                            "author_id": message.author.id,
                            "author_name": str(message.author),
                            "author_display_name": message.author.display_name,
                            "is_bot": message.author.bot,
                            "is_target_user": message.author.id == TARGET_USER_ID,
                            "content": message.content,
                            "message_id": message.id,
                            "has_attachments": len(message.attachments) > 0,
                            "attachment_urls": [a.url for a in message.attachments],
                            "replied_to": message.reference.message_id if message.reference else None,
                            "mentions": [m.id for m in message.mentions],
                            "reactions": [
                                {"emoji": str(r.emoji), "count": r.count}
                                for r in message.reactions
                            ] if message.reactions else []
                        }
                        
                        self.messages_by_channel[channel.name].append(msg_data)
                        
                        # Track user stats
                        self.user_stats[message.author.id]["messages"] += 1
                        self.user_stats[message.author.id]["name"] = str(message.author)
                        self.user_stats[message.author.id]["is_bot"] = message.author.bot
                        
                        if message.author.bot:
                            self.bot_ids.add(message.author.id)
                        
                        msg_count += 1
                        
                        if msg_count % 500 == 0:
                            print(f"      ... {msg_count} messages extracted")
                    
                    total_messages += msg_count
                    print(f"    ✓ {msg_count} messages from #{channel.name}")
                            
                except discord.Forbidden:
                    print(f"    ⚠️  No access to {channel.name}")
                except Exception as e:
                    print(f"    ❌ Error in {channel.name}: {e}")
        
        print()
        print(f"✓ Total messages extracted: {total_messages}")
        
        await self.save_results()
        await self.close()
    
    async def save_results(self):
        output_dir = Path(__file__).parent.parent / "data_exports" / "analysis"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Combine all messages
        all_messages = []
        for channel_msgs in self.messages_by_channel.values():
            all_messages.extend(channel_msgs)
        
        # Sort by timestamp
        all_messages.sort(key=lambda x: x['timestamp'])
        
        # Save JSON (full data)
        json_path = output_dir / "full_channel_context_raw.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "metadata": {
                    "extraction_date": datetime.now(timezone.utc).isoformat(),
                    "start_date": START_DATE.isoformat(),
                    "end_date": END_DATE.isoformat(),
                    "target_user_id": TARGET_USER_ID,
                    "channels": TARGET_CHANNELS,
                    "total_messages": len(all_messages),
                    "unique_users": len(self.user_stats),
                    "bot_count": len(self.bot_ids)
                },
                "user_stats": {
                    str(uid): stats for uid, stats in self.user_stats.items()
                },
                "messages": all_messages
            }, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved raw data: {json_path}")
        
        # Save readable markdown
        md_path = output_dir / "full_channel_context_readable.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("# Full Channel Context Analysis\n\n")
            f.write(f"**Target User ID:** {TARGET_USER_ID}\n")
            f.write(f"**Date Range:** {START_DATE.date()} to {END_DATE.date()}\n")
            f.write(f"**Channels:** {', '.join(self.messages_by_channel.keys())}\n")
            f.write(f"**Total Messages:** {len(all_messages)}\n")
            f.write(f"**Unique Users:** {len(self.user_stats)}\n")
            f.write(f"**Bots:** {len(self.bot_ids)}\n\n")
            
            f.write("---\n\n")
            f.write("## Participant Summary\n\n")
            f.write("| User | Messages | Type |\n")
            f.write("|------|----------|------|\n")
            
            # Sort by message count
            sorted_users = sorted(
                self.user_stats.items(),
                key=lambda x: x[1]['messages'],
                reverse=True
            )
            
            for uid, stats in sorted_users:
                user_type = "🤖 BOT" if stats.get('is_bot') else "👤 Human"
                if uid == TARGET_USER_ID:
                    user_type = "⚠️ **TARGET**"
                f.write(f"| {stats['name']} | {stats['messages']} | {user_type} |\n")
            
            f.write("\n---\n\n")
            f.write("## Message Timeline\n\n")
            
            # Group by date
            by_date = defaultdict(list)
            for msg in all_messages:
                date = msg['timestamp'][:10]
                by_date[date].append(msg)
            
            for date in sorted(by_date.keys()):
                day_msgs = by_date[date]
                target_count = sum(1 for m in day_msgs if m['is_target_user'])
                f.write(f"### {date} ({len(day_msgs)} messages, {target_count} from target)\n\n")
                
                for msg in day_msgs:
                    time = msg['timestamp'][11:19]
                    is_target = "**⚠️**" if msg['is_target_user'] else ""
                    is_bot = "🤖" if msg['is_bot'] else ""
                    
                    f.write(f"#### [{time}] {is_bot}{is_target} {msg['author_display_name']}\n")
                    f.write(f"*#{msg['channel_name']}*\n\n")
                    
                    if msg['replied_to']:
                        f.write(f"*↩️ Replying to message {msg['replied_to']}*\n\n")
                    
                    # Truncate very long messages
                    content = msg['content']
                    if len(content) > 2000:
                        content = content[:2000] + "\n\n*[Message truncated - see JSON for full content]*"
                    
                    f.write(f"{content}\n\n")
                    
                    if msg['reactions']:
                        reactions = " ".join([f"{r['emoji']}×{r['count']}" for r in msg['reactions']])
                        f.write(f"*Reactions: {reactions}*\n\n")
                    
                    f.write("---\n\n")
        
        print(f"✓ Saved readable format: {md_path}")
        
        # Print summary
        self._print_summary(all_messages)
    
    def _print_summary(self, all_messages):
        print()
        print("=" * 80)
        print("EXTRACTION SUMMARY")
        print("=" * 80)
        
        print(f"\nTotal messages: {len(all_messages)}")
        print(f"Unique users: {len(self.user_stats)}")
        print(f"Bots: {len(self.bot_ids)}")
        
        print("\nTop 10 users by message count:")
        sorted_users = sorted(
            self.user_stats.items(),
            key=lambda x: x[1]['messages'],
            reverse=True
        )[:10]
        
        for uid, stats in sorted_users:
            marker = " ⚠️ TARGET" if uid == TARGET_USER_ID else ""
            bot = " (BOT)" if stats.get('is_bot') else ""
            print(f"  {stats['name']}{bot}: {stats['messages']} messages{marker}")
        
        # Target user stats
        target_msgs = [m for m in all_messages if m['is_target_user']]
        print(f"\nTarget user ({TARGET_USER_ID}):")
        print(f"  Total messages: {len(target_msgs)}")
        
        if target_msgs:
            print(f"  First message: {target_msgs[0]['timestamp'][:10]}")
            print(f"  Last message: {target_msgs[-1]['timestamp'][:10]}")
            
            # Messages per channel
            by_channel = defaultdict(int)
            for m in target_msgs:
                by_channel[m['channel_name']] += 1
            print(f"  By channel:")
            for ch, count in by_channel.items():
                print(f"    #{ch}: {count}")
        
        # Bot interaction analysis
        print("\nBot interactions with target user:")
        bot_replies_to_target = 0
        target_replies_to_bots = 0
        
        msg_by_id = {m['message_id']: m for m in all_messages}
        for msg in all_messages:
            if msg['replied_to'] and msg['replied_to'] in msg_by_id:
                original = msg_by_id[msg['replied_to']]
                if msg['is_bot'] and original['is_target_user']:
                    bot_replies_to_target += 1
                elif msg['is_target_user'] and original['is_bot']:
                    target_replies_to_bots += 1
        
        print(f"  Bot replies to target: {bot_replies_to_target}")
        print(f"  Target replies to bots: {target_replies_to_bots}")


async def main():
    print("=" * 80)
    print("FULL CHANNEL CONTEXT EXTRACTOR")
    print("For Psychological Analysis - All Participants")
    print("=" * 80)
    print()
    
    client = FullChannelExtractor()
    
    try:
        await client.start(TOKEN)
    except discord.LoginFailure:
        print("❌ Error: Invalid bot token")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if not client.is_closed():
            await client.close()


if __name__ == "__main__":
    asyncio.run(main())
