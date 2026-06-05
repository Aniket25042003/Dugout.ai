"""
Ollama HTTP client for Dugout.ai Commentary Engine.
"""

import logging
import httpx
from typing import Optional

logger = logging.getLogger("ai-orchestrator-llm")

OLLAMA_URL = "http://localhost:11434"

class OllamaClient:
    """Async client for local Ollama instance."""

    def __init__(self, base_url: str = OLLAMA_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def check_health(self) -> bool:
        """Check if Ollama server is up and responsive."""
        try:
            response = await self.client.get("/")
            return response.status_code == 200
        except Exception:
            return False

    async def check_model_available(self, model: str) -> bool:
        """Check if the requested model is pulled and available."""
        try:
            response = await self.client.get("/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                for m in models:
                    if m.get("name") == model or m.get("name").startswith(model + ":"):
                        return True
            return False
        except Exception as e:
            logger.error("Failed to check models with Ollama: %s", e)
            return False

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, model: str = "llama3.2:1b") -> dict:
        """
        Generate text completion for the prompt.
        Returns a dict containing:
        - 'text': the generated text
        - 'prompt_tokens': tokens used in prompt (if available)
        - 'completion_tokens': tokens used in completion (if available)
        - 'duration_ms': generation time in ms
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        import time
        try:
            start_time = time.perf_counter()
            response = await self.client.post("/api/generate", json=payload)
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            if response.status_code != 200:
                logger.error("Ollama error: %s", response.text)
                return {"text": "", "error": f"HTTP {response.status_code}", "duration_ms": duration_ms}

            data = response.json()
            return {
                "text": data.get("response", "").strip(),
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "duration_ms": duration_ms,
            }

        except Exception as e:
            logger.error("Failed to generate with Ollama: %s", e)
            return {"text": "", "error": str(e), "duration_ms": 0}
