"""
One-time cleanup script to remove legacy [WHISPER_IMAGE:...] markers from PostgreSQL chat history.
"""
import asyncio
import asyncpg
import re
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://whisper:password@localhost:5432/whisperengine_v2")

async def cleanup_postgres_markers():
    print(f"Connecting to PostgreSQL...")
    try:
        conn = await asyncpg.connect(POSTGRES_URL)
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    print("Connected. Searching for legacy markers...")
    
    # Find rows with markers
    rows = await conn.fetch("""
        SELECT id, content 
        FROM v2_chat_history 
        WHERE content LIKE '%[WHISPER_IMAGE:%'
    """)
    
    print(f"Found {len(rows)} rows with markers.")
    
    updated_count = 0
    
    for row in rows:
        msg_id = row['id']
        content = row['content']
        
        # Remove the marker using regex
        new_content = re.sub(r'\[WHISPER_IMAGE:[a-f0-9]+\]', '', content).strip()
        
        if new_content != content:
            await conn.execute("""
                UPDATE v2_chat_history 
                SET content = $1 
                WHERE id = $2
            """, new_content, msg_id)
            updated_count += 1
            print(f"  Cleaned message {msg_id}")
            
    print(f"\n✅ Cleanup complete. Updated {updated_count} rows.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(cleanup_postgres_markers())
