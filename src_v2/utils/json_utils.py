import re
import json
from typing import Optional, Any, Union, Dict, List
from loguru import logger

def extract_json_from_text(text: str) -> Optional[Union[Dict, List]]:
    """
    Robustly extracts and parses JSON from text that may contain Markdown code blocks
    or other surrounding text.
    
    Args:
        text: The raw text from LLM
        
    Returns:
        Parsed JSON object (dict or list) or None if parsing fails
    """
    if not text:
        return None
        
    text = text.strip()
    
    # 1. Try to find JSON within code blocks
    # Matches ```json ... ``` or just ``` ... ```
    code_block_pattern = r"```(?:json)?\s*(.*?)\s*```"
    match = re.search(code_block_pattern, text, re.DOTALL | re.IGNORECASE)
    
    if match:
        json_str = match.group(1)
    else:
        # 2. Fallback: Try to find the first outer-most JSON object/array
        # This is a simple heuristic: find first { or [ and last } or ]
        
        # Find first potential start
        first_brace = text.find('{')
        first_bracket = text.find('[')
        
        start_idx = -1
        end_char = ''
        
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            start_idx = first_brace
            end_char = '}'
        elif first_bracket != -1:
            start_idx = first_bracket
            end_char = ']'
            
        if start_idx != -1:
            end_idx = text.rfind(end_char)
            if end_idx != -1 and end_idx > start_idx:
                json_str = text[start_idx:end_idx+1]
            else:
                # If we found a start but no end, try parsing the whole thing (unlikely to work but worth a shot)
                json_str = text
        else:
            # No brackets found, try parsing the whole thing
            json_str = text

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.debug(f"Failed to parse JSON from text: {e}")
        return None
