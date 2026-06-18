"""
File: services/ai-orchestrator/llm_client.py
Layer: Worker — Local LLM Client
Purpose: Wraps Ollama's HTTP API for commentary text generation.
         CommentaryEngine calls this client before falling back to templates.
Dependencies: httpx AsyncClient, local Ollama server at OLLAMA_URL.
"""

import logging
import httpx
from typing import Optional

logger = logging.getLogger("ai-orchestrator-llm")

OLLAMA_URL = "http://localhost:11434"

class OllamaClient:
    """
    Async client for a local Ollama instance.

    Attributes:
        base_url (str): Base URL for the Ollama HTTP server.
        client (httpx.AsyncClient): Reused async HTTP client with generation timeout.
    """

    def __init__(self, base_url: str = OLLAMA_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def close(self):
        """
        Closes the underlying HTTP client.

        Side Effects:
            Releases httpx connection resources.
        """
        await self.client.aclose()

    async def check_health(self) -> bool:
        """
        Checks whether the Ollama server is reachable.

        Returns:
            bool: True when Ollama responds with HTTP 200, otherwise False.
        """
        try:
            response = await self.client.get("/")
            return response.status_code == 200
        except Exception:
            return False

    async def check_model_available(self, model: str) -> bool:
        """
        Checks whether a requested model is available in Ollama.

        Args:
            model (str): Model name or prefix, for example ``llama3.2:1b``.

        Returns:
            bool: True when the model appears in Ollama's tag list.
        """
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
        Generates a non-streaming text completion from Ollama.

        Args:
            prompt (str): User prompt sent to the model.
            system_prompt (Optional[str]): Optional system instruction for style/context.
            model (str): Ollama model name to use for generation.

        Returns:
            dict: Generated text, token counts when available, duration in ms, and
                an ``error`` field when generation fails.

        Side Effects:
            Performs an HTTP POST to the local Ollama API.
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
