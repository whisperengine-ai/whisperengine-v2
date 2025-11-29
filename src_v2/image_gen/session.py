import json
import re
import redis.asyncio as redis
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger
from src_v2.config.settings import settings


# Patterns that indicate the user is refining a previous image
REFINEMENT_PATTERNS = [
    r"^same\s+but",           # "same but with glasses"
    r"^keep\s+",              # "keep the hair, change the dress"
    r"^change\s+the",         # "change the background"
    r"^remove\s+the",         # "remove the hat"
    r"^add\s+",               # "add a scarf"
    r"^make\s+(?:it|her|him|them|me)", # "make it darker", "make her smile", "make me look more X"
    r"^try\s+(?:again|with)", # "try again with blue eyes"
    r"^more\s+",              # "more dramatic lighting"
    r"^less\s+",              # "less saturated"
    r"^different\s+",         # "different outfit"
    r"like\s+(?:the\s+)?(?:last|before|previous)", # "like the last one but..."
    r"look\s+more",           # "look more hispanic", "look more like X"
]


def is_refinement_request(prompt: str) -> bool:
    """
    Detect if the prompt is a refinement of a previous generation.
    Returns True if the prompt matches common refinement patterns.
    """
    prompt_lower = prompt.lower().strip()
    
    # Strip Discord reply context prefix so ^anchored patterns work
    # e.g. "[Replying to Bot's image [with image]]\nmake me look more hispanic"
    if prompt_lower.startswith("[replying to"):
        # Find the end of the reply prefix and extract the actual message
        newline_idx = prompt_lower.find("\n")
        if newline_idx != -1:
            prompt_lower = prompt_lower[newline_idx + 1:].strip()
    
    for pattern in REFINEMENT_PATTERNS:
        if re.search(pattern, prompt_lower):
            return True
    
    return False


def parse_refinement_instructions(prompt: str) -> Tuple[List[str], List[str], str]:
    """
    Parse a refinement prompt to extract:
    - elements to keep (confirmed)
    - elements to remove/change (rejected)  
    - the actual modification request
    
    Returns: (keep_elements, remove_elements, modification)
    """
    prompt_lower = prompt.lower().strip()
    keep_elements = []
    remove_elements = []
    modification = prompt
    
    # Extract "keep X" patterns
    keep_matches = re.findall(r"keep\s+(?:the\s+)?([^,\.]+?)(?:,|\.|$|but)", prompt_lower)
    keep_elements.extend([m.strip() for m in keep_matches if m.strip()])
    
    # Extract "remove X" or "no X" patterns  
    remove_matches = re.findall(r"(?:remove|no|without|lose)\s+(?:the\s+)?([^,\.]+?)(?:,|\.|$)", prompt_lower)
    remove_elements.extend([m.strip() for m in remove_matches if m.strip()])
    
    # Extract "change X to Y" patterns - X goes to remove, Y goes to modification
    change_matches = re.findall(r"change\s+(?:the\s+)?([^,\.]+?)\s+to\s+([^,\.]+?)(?:,|\.|$)", prompt_lower)
    for old, _new in change_matches:
        remove_elements.append(old.strip())
    
    return keep_elements, remove_elements, modification


def apply_refinement_to_prompt(previous_prompt: str, refinement: str, keep: List[str], remove: List[str]) -> str:
    """
    Intelligently merge a refinement request with the previous prompt.
    
    Strategy:
    1. Start with previous prompt
    2. Remove explicitly rejected elements
    3. Append modification instruction
    4. Add emphasis on kept elements
    """
    result = previous_prompt
    
    # Remove rejected elements (simple string matching for now)
    for element in remove:
        # Try to remove the element and surrounding punctuation
        patterns = [
            rf",?\s*{re.escape(element)}\s*,?",
            rf"\b{re.escape(element)}\b",
        ]
        for pattern in patterns:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    
    # Clean up any double commas or spaces
    result = re.sub(r",\s*,", ",", result)
    result = re.sub(r"\s+", " ", result).strip()
    result = result.strip(",").strip()
    
    # Append the refinement instruction
    if refinement and len(refinement) > 3:
        result = f"{result}. {refinement}"
    
    # Emphasize kept elements by moving them to the end with emphasis
    if keep:
        kept_str = ", ".join(keep)
        result = f"{result}. Maintain: {kept_str}"
    
    return result


class ImageSessionManager:
    """
    Manages image generation sessions to support iterative refinement.
    Stores the last prompt, seed, and parameters for each user.
    """
    
    def __init__(self):
        self._redis = None
        self._ttl = 3600  # 1 hour session
        
    async def _get_redis(self):
        if not self._redis:
            self._redis = redis.from_url(settings.REDIS_URL)
        return self._redis
        
    async def save_session(self, user_id: str, prompt: str, seed: int, params: Dict[str, Any]) -> None:
        """
        Saves the current generation state.
        """
        try:
            r = await self._get_redis()
            key = f"image_session:{user_id}"
            
            data = {
                "prompt": prompt,
                "seed": seed,
                "params": params,
                "timestamp": params.get("timestamp")
            }
            
            await r.setex(key, self._ttl, json.dumps(data))
            logger.debug(f"Saved image session for user {user_id} (seed: {seed})")
            
        except Exception as e:
            logger.error(f"Failed to save image session: {e}")
            
    async def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the last generation state.
        """
        try:
            r = await self._get_redis()
            key = f"image_session:{user_id}"
            data = await r.get(key)
            
            if data:
                return json.loads(data)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get image session: {e}")
            return None
            
    async def clear_session(self, user_id: str) -> None:
        """
        Clears the session (e.g. when starting a completely new topic).
        """
        try:
            r = await self._get_redis()
            key = f"image_session:{user_id}"
            await r.delete(key)
        except Exception as e:
            logger.error(f"Failed to clear image session: {e}")

    async def has_recent_session(self, user_id: str) -> bool:
        """
        Check if user has a recent image generation session (within TTL).
        Used for refinement detection.
        """
        session = await self.get_session(user_id)
        return session is not None

# Global instance
image_session = ImageSessionManager()
