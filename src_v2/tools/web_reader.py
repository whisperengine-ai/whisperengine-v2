from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
import httpx
from bs4 import BeautifulSoup
from loguru import logger
import re
from urllib.parse import urlparse, parse_qs

try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
    HAS_YOUTUBE = True
except ImportError:
    HAS_YOUTUBE = False

class ReadWebPageInput(BaseModel):
    """Input schema for reading a web page."""
    url: str = Field(description="The URL of the web page to read")

class ReadWebPageTool(BaseTool):
    name: str = "read_web_page"
    description: str = """Read the content of a specific web page URL.
    
USE THIS WHEN:
- The user provides a specific URL and asks you to read, summarize, or discuss it.
- You need to get the full content of a page found via web search.
- The user provides a YouTube URL (will attempt to fetch transcript).

DO NOT USE FOR:
- General searching (use web_search instead).
- URLs that are not publicly accessible.
"""
    args_schema: Type[BaseModel] = ReadWebPageInput

    def _extract_youtube_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        parsed = urlparse(url)
        if parsed.hostname in ('www.youtube.com', 'youtube.com'):
            if parsed.path == '/watch':
                return parse_qs(parsed.query).get('v', [None])[0]
        if parsed.hostname == 'youtu.be':
            return parsed.path[1:]
        return None

    async def _get_youtube_transcript(self, video_id: str) -> Optional[str]:
        """Fetch transcript for a YouTube video. Returns None if not available."""
        if not HAS_YOUTUBE:
            return None
            
        try:
            # Run in executor since it's synchronous
            import asyncio
            loop = asyncio.get_running_loop()
            
            # Note: In newer versions, YouTubeTranscriptApi is a class we instantiate
            transcript_list = await loop.run_in_executor(
                None, 
                lambda: YouTubeTranscriptApi().fetch(video_id)
            )
            
            # Format transcript
            text_parts = []
            for entry in transcript_list:
                # entry is FetchedTranscriptSnippet object with .text attribute
                text_parts.append(entry.text)
            
            full_text = " ".join(text_parts)
            return f"YouTube Video Transcript (ID: {video_id}):\n\n{full_text}"
            
        except (TranscriptsDisabled, NoTranscriptFound):
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch transcript for {video_id}: {e}")
            return None

    def _run(self, url: str) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, url: str) -> str:
        """
        Asynchronously fetch and parse a web page.
        """
        # Basic validation
        if not url.startswith(('http://', 'https://')):
            return "Error: URL must start with http:// or https://"

        # Check for YouTube URL first
        video_id = self._extract_youtube_id(url)
        transcript_failed = False
        if video_id:
            transcript = await self._get_youtube_transcript(video_id)
            if transcript:
                return transcript
            transcript_failed = True
            # If no transcript, fall through to standard page reading to get title/description
            
        # Security check: Prevent access to local network/metadata services (SSRF protection)
        # This is a basic check. For production, use a more robust library or proxy.
        # We block common private IP ranges and localhost.
        # Note: This regex is not exhaustive but covers common cases.
        # 10.x.x.x, 172.16-31.x.x, 192.168.x.x, 127.x.x.x, 169.254.x.x
        private_ip_pattern = re.compile(
            r'^(?:https?://)?(?:(?:10|127)(?:\.\d{1,3}){3}|'
            r'(?:169\.254|192\.168)(?:\.\d{1,3}){2}|'
            r'172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}|'
            r'localhost)'
        )
        
        if private_ip_pattern.match(url):
             return "Error: Access to private or local network URLs is restricted for security reasons."

        try:
            # Use a standard browser User-Agent to avoid blocking
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                # Check content type - allow text/* and application/xhtml+xml
                content_type = response.headers.get("content-type", "").lower()
                if not (content_type.startswith("text/") or "xml" in content_type or "json" in content_type):
                     # Try to proceed if it looks like HTML but header is weird, otherwise warn
                     pass
                
                # Parse HTML using response.content for better encoding handling
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract metadata (Title & Description) - especially useful for YouTube/Social sites
                meta_info = []
                
                if transcript_failed:
                    meta_info.append("[NOTE: YouTube transcript unavailable. Showing video metadata below.]")

                # Title
                title = soup.title.string if soup.title else ""
                og_title = soup.find("meta", property="og:title")
                twitter_title = soup.find("meta", attrs={"name": "twitter:title"})
                
                if og_title and og_title.get("content"):
                    title = og_title["content"]
                elif twitter_title and twitter_title.get("content"):
                    title = twitter_title["content"]
                    
                if title:
                    meta_info.append(f"Title: {title}")
                    
                # Description
                desc = soup.find("meta", attrs={"name": "description"})
                og_desc = soup.find("meta", property="og:description")
                twitter_desc = soup.find("meta", attrs={"name": "twitter:description"})
                
                description = ""
                if og_desc and og_desc.get("content"):
                    description = og_desc["content"]
                elif twitter_desc and twitter_desc.get("content"):
                    description = twitter_desc["content"]
                elif desc and desc.get("content"):
                    description = desc["content"]
                
                if description:
                    meta_info.append(f"Description: {description}")
                
                # Remove script, style, and other non-content elements
                for script in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript", "svg"]):
                    script.decompose()
                
                # Get text
                text = soup.get_text()
                
                # Break into lines and remove leading/trailing space on each
                lines = (line.strip() for line in text.splitlines())
                # Break multi-headlines into a line each
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                # Drop blank lines
                body_text = '\n'.join(chunk for chunk in chunks if chunk)
                
                # Combine metadata and body
                full_content = ""
                if meta_info:
                    full_content += "\n".join(meta_info) + "\n\n" + "-"*20 + "\n\n"
                
                full_content += body_text
                
                # Truncate if too long (e.g. 10k chars)
                if len(full_content) > 10000:
                    full_content = full_content[:10000] + "\n...[Content truncated due to length]..."
                
                return f"Content of {url}:\n\n{full_content}"
                
        except httpx.HTTPStatusError as e:
            return f"Error reading page: HTTP {e.response.status_code}"
        except httpx.RequestError as e:
            return f"Error reading page: {str(e)}"
        except Exception as e:
            logger.error(f"Web page read failed: {e}")
            return f"Error reading page: {str(e)}"

# Export singleton
read_web_page_tool = ReadWebPageTool()
