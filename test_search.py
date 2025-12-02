import asyncio
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from src_v2.tools.web_search import web_search_tool

async def main():
    print("Testing WebSearchTool...")
    query = "latest ocean conservation news"
    print(f"Query: {query}")
    
    try:
        results = await web_search_tool._arun(query, max_results=3)
        print("\nResults:")
        print(results)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
