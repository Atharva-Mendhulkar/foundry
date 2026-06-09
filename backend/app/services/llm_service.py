import httpx
import json
import logging
from typing import AsyncGenerator, Dict, Any, List

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://ollama:11434"

class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_URL):
        self.base_url = base_url

    async def generate(self, prompt: str, system: str = "", model: str = "qwen2.5", temperature: float = 0.0, format: str = None) -> str:
        """Generate text using Ollama."""
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if format:
            payload["format"] = format
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=120.0)
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
            except Exception as e:
                logger.error(f"Error in Ollama generate: {e}")
                raise e

    async def stream(self, prompt: str, system: str = "", model: str = "qwen2.5", temperature: float = 0.0) -> AsyncGenerator[str, None]:
        """Stream text generation using Ollama."""
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": True,
            "options": {
                "temperature": temperature
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("POST", url, json=payload, timeout=120.0) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.error(f"Error in Ollama stream: {e}")
                raise e

    async def embed(self, text: str, model: str = "nomic-embed-text") -> List[float]:
        """Generate embeddings using Ollama."""
        url = f"{self.base_url}/api/embeddings"
        
        payload = {
            "model": model,
            "prompt": text
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=60.0)
                response.raise_for_status()
                result = response.json()
                return result.get("embedding", [])
            except Exception as e:
                logger.error(f"Error in Ollama embed: {e}")
                raise e

ollama_client = OllamaClient()
