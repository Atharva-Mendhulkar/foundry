import logging
import json
from app.agents.state import FoundryState
from app.services.llm_service import ollama_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an industrial data extraction AI.
Extract all equipment, failure modes, and procedures from the provided text.
Format your output EXACTLY as valid JSON matching this schema:
{
  "entities": [
    {
      "name": "string",
      "type": "Equipment" | "Failure" | "Procedure",
      "context": "Brief context about where this was found"
    }
  ]
}
Return ONLY the JSON. No markdown formatting, no explanations.
"""

async def entity_extraction_node(state: FoundryState) -> dict:
    """Extract entities from raw text using LLM."""
    logger.info(f"entity_extraction_node for job {state['job_id']}")
    
    raw_text = state.get("raw_text", "")
    if not raw_text:
        return {"error": "No raw text available for extraction", "status": "error"}
        
    prompt = f"Text to analyze:\n\n{raw_text[:8000]}" # Limit text to fit context window

    try:
        # We'll try up to 2 times to get valid JSON
        for attempt in range(2):
            response = await ollama_client.generate(
                prompt=prompt,
                system=SYSTEM_PROMPT,
                format="json"
            )
            
            try:
                # Clean up response if needed
                text_response = response.strip()
                if text_response.startswith("```json"):
                    text_response = text_response[7:-3].strip()
                    
                data = json.loads(text_response)
                
                # Validation
                if "entities" in data and isinstance(data["entities"], list):
                    return {
                        "extracted_entities": data["entities"],
                        "current_stage": "embed_document"
                    }
                    
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON on attempt {attempt+1}")
                continue
                
        return {"error": "Failed to extract valid JSON entities after retries", "status": "error"}
        
    except Exception as e:
        logger.error(f"Error in entity_extraction_node: {e}")
        return {"error": str(e), "status": "error"}
