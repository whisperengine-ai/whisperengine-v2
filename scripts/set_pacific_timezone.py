#!/usr/bin/env python3
"""Set TZ=America/Los_Angeles for all bot .env files."""

import re
from pathlib import Path

# Find all .env.* files
env_dir = Path(__file__).parent.parent
bot_names = [
    "elena", "nottaylor", "dotty", "aria", "dream", "jake", 
    "marcus", "ryan", "sophia", "gabriel", "aethys", "aetheris"
]

TIMEZONE = "America/Los_Angeles"

for bot in bot_names:
    env_file = env_dir / f".env.{bot}"
    if not env_file.exists():
        print(f"⚠️  {env_file.name} not found, skipping")
        continue
    
    content = env_file.read_text()
    
    # Check if TZ= exists
    if re.search(r'^TZ=', content, re.MULTILINE):
        # Update existing TZ line
        new_content = re.sub(r'^TZ=.*$', f'TZ={TIMEZONE}', content, flags=re.MULTILINE)
        if new_content != content:
            env_file.write_text(new_content)
            print(f"✅ Updated TZ={TIMEZONE} in {env_file.name}")
        else:
            print(f"⏭️  {env_file.name} already has TZ={TIMEZONE}")
    else:
        # Add TZ after other settings (near top, after feature flags)
        # Find a good place to insert - after DISCORD_BOT_NAME or at end of file
        lines = content.split('\n')
        inserted = False
        new_lines = []
        for i, line in enumerate(lines):
            new_lines.append(line)
            if line.startswith('DISCORD_BOT_NAME=') and not inserted:
                new_lines.append(f'TZ={TIMEZONE}')
                inserted = True
        
        if not inserted:
            new_lines.append(f'TZ={TIMEZONE}')
        
        env_file.write_text('\n'.join(new_lines))
        print(f"✅ Added TZ={TIMEZONE} to {env_file.name}")

print("\n🎯 Done! All bots set to Pacific time.")
print("⚠️  Remember: .env changes require stop/start (not restart):")
print("   ./bot.sh stop all && ./bot.sh up all")
