#!/usr/bin/env python3
"""
Extract Discord messages from missing period (Sept-Oct 2025)
to fill in the data gap from Qdrant vector memory wipe.

Usage: python scripts/extract_discord_missing_data.py
"""

import discord
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import os

# Load nottaylor bot token (the bot from the ethics incident)
env_path = Path(__file__).parent.parent / ".env.nottaylor"
load_dotenv(env_path)

TOKEN = os.getenv("DISCORD_TOKEN")  # Note: uses DISCORD_TOKEN, not DISCORD_BOT_TOKEN
if not TOKEN:
    # Try loading from .env.aethys as fallback
    env_path = Path(__file__).parent.parent / ".env.aethys"
    load_dotenv(env_path)
    TOKEN = os.getenv("DISCORD_TOKEN")

USER_ID = 932729340968443944

# Date range for missing data
START_DATE = datetime(2025, 9, 1, tzinfo=timezone.utc)
END_DATE = datetime(2025, 10, 30, tzinfo=timezone.utc)

class MessageExtractor(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.messages_found = []
        
    async def on_ready(self):
        print(f"✓ Logged in as {self.user}")
        print(f"✓ Searching for messages from user {USER_ID}")
        print(f"✓ Date range: {START_DATE.date()} to {END_DATE.date()}")
        print()
        
        # Search all text channels the bot has access to
        for guild in self.guilds:
            print(f"📂 Searching guild: {guild.name}")
            
            for channel in guild.text_channels:
                try:
                    # Check permissions
                    permissions = channel.permissions_for(guild.me)
                    if not permissions.read_message_history:
                        continue
                    
                    print(f"  📝 Checking channel: {channel.name}")
                    
                    # Search messages in date range
                    async for message in channel.history(
                        after=START_DATE,
                        before=END_DATE,
                        limit=None,
                        oldest_first=True
                    ):
                        if message.author.id == USER_ID:
                            self.messages_found.append({
                                "timestamp": message.created_at.isoformat(),
                                "channel": channel.name,
                                "guild": guild.name,
                                "author_name": str(message.author),
                                "content": message.content,
                                "message_id": message.id,
                                "has_attachments": len(message.attachments) > 0,
                                "replied_to": message.reference.message_id if message.reference else None
                            })
                            
                except discord.Forbidden:
                    print(f"    ⚠️  No access to {channel.name}")
                except Exception as e:
                    print(f"    ❌ Error in {channel.name}: {e}")
        
        print()
        print(f"✓ Found {len(self.messages_found)} messages")
        
        # Save results
        await self.save_results()
        
        # Close connection
        await self.close()
    
    async def save_results(self):
        output_dir = Path(__file__).parent.parent / "data_exports" / "analysis"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON
        json_path = output_dir / "discord_missing_period_raw.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.messages_found, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved raw data: {json_path}")
        
        # Save readable markdown
        md_path = output_dir / "discord_missing_period_readable.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# Discord Messages: Missing Period Analysis\n\n")
            f.write(f"**User ID:** {USER_ID}\n")
            f.write(f"**Date Range:** {START_DATE.date()} to {END_DATE.date()}\n")
            f.write(f"**Total Messages Found:** {len(self.messages_found)}\n\n")
            f.write("---\n\n")
            
            # Group by date
            by_date = {}
            for msg in self.messages_found:
                date = msg['timestamp'][:10]
                if date not in by_date:
                    by_date[date] = []
                by_date[date].append(msg)
            
            # Write chronologically
            for date in sorted(by_date.keys()):
                f.write(f"## {date} ({len(by_date[date])} messages)\n\n")
                
                for msg in by_date[date]:
                    time = msg['timestamp'][11:19]
                    f.write(f"### [{time}] {msg['author_name']}\n")
                    f.write(f"**Channel:** #{msg['channel']} ({msg['guild']})\n\n")
                    
                    if msg['replied_to']:
                        f.write(f"*[Replying to message {msg['replied_to']}]*\n\n")
                    
                    f.write(f"{msg['content']}\n\n")
                    
                    if msg['has_attachments']:
                        f.write("*[Has attachments]*\n\n")
                    
                    f.write("---\n\n")
        
        print(f"✓ Saved readable format: {md_path}")
        
        # Print summary statistics
        print()
        print("=" * 80)
        print("SUMMARY STATISTICS")
        print("=" * 80)
        
        if self.messages_found:
            by_date = {}
            for msg in self.messages_found:
                date = msg['timestamp'][:10]
                by_date[date] = by_date.get(date, 0) + 1
            
            print(f"\nMessages per day:")
            for date in sorted(by_date.keys()):
                print(f"  {date}: {by_date[date]} messages")
            
            # First and last message
            first = self.messages_found[0]
            last = self.messages_found[-1]
            print(f"\nFirst message: {first['timestamp'][:10]}")
            print(f"Last message: {last['timestamp'][:10]}")
            print(f"\nFirst message content preview:")
            print(f"  {first['content'][:200]}...")
        else:
            print("\n⚠️  No messages found in date range")
            print("This could mean:")
            print("  - User hadn't joined yet")
            print("  - Messages were in channels bot can't access")
            print("  - Different bot was used during this period")

async def main():
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN not found in .env.nottaylor or .env.aethys")
        return
    
    print("=" * 80)
    print("DISCORD MESSAGE EXTRACTOR - Missing Period Analysis")
    print("=" * 80)
    print()
    
    client = MessageExtractor()
    
    try:
        await client.start(TOKEN)
    except discord.LoginFailure:
        print("❌ Error: Invalid bot token")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if not client.is_closed():
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())
