"""
Piper TTS Client for Dugout.ai Commentary Engine.
Automatically downloads voice model files if not present.
"""

import logging
import os
import wave
import httpx
from typing import Optional
from piper import PiperVoice

logger = logging.getLogger("ai-orchestrator-tts")

DEFAULT_MODEL_NAME = "en_US-lessac-medium"
MODEL_URLS = {
    "en_US-lessac-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx?download=true",
    "en_US-lessac-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json?download=true"
}

class TTSClient:
    """Piper TTS Wrapper client that handles voice synthesis."""

    def __init__(self, models_dir: str = None):
        if not models_dir:
            models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        self.models_dir = models_dir
        self.model_path = os.path.join(self.models_dir, f"{DEFAULT_MODEL_NAME}.onnx")
        self.config_path = os.path.join(self.models_dir, f"{DEFAULT_MODEL_NAME}.onnx.json")
        self._voice: Optional[PiperVoice] = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Download models if missing and load the Piper voice."""
        if self._initialized:
            return True

        os.makedirs(self.models_dir, exist_ok=True)
        
        # Download missing files
        async with httpx.AsyncClient(timeout=600.0) as client:
            for filename, url in MODEL_URLS.items():
                dest_path = os.path.join(self.models_dir, filename)
                if not os.path.isfile(dest_path):
                    logger.info("Downloading TTS asset %s...", filename)
                    try:
                        # Follow redirects if Hugging Face does so
                        response = await client.get(url, follow_redirects=True)
                        if response.status_code == 200:
                            with open(dest_path, "wb") as f:
                                f.write(response.content)
                            logger.info("Downloaded %s successfully.", filename)
                        else:
                            logger.error("Failed to download %s: HTTP %d", filename, response.status_code)
                            return False
                    except Exception as e:
                        logger.error("Error downloading %s: %s", filename, e)
                        return False

        # Load Piper voice
        try:
            logger.info("Loading Piper voice model from %s...", self.model_path)
            # Load in executor to avoid blocking the main event loop
            import asyncio
            loop = asyncio.get_event_loop()
            self._voice = await loop.run_in_executor(
                None, 
                lambda: PiperVoice.load(self.model_path, self.config_path)
            )
            self._initialized = True
            logger.info("Piper voice model loaded successfully.")
            return True
        except Exception as e:
            logger.error("Failed to load Piper voice model: %s", e)
            return False

    async def synthesize(self, text: str, output_path: str) -> bool:
        """Synthesize text to WAV file."""
        if not self._initialized:
            success = await self.initialize()
            if not success:
                logger.error("Cannot synthesize, TTS not initialized.")
                return False

        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            import asyncio
            loop = asyncio.get_event_loop()

            def run_synthesis():
                with wave.open(output_path, "wb") as wav_file:
                    self._voice.synthesize_wav(text, wav_file)

            # Synthesize in executor to avoid blocking FastAPI
            await loop.run_in_executor(None, run_synthesis)
            logger.info("Synthesized audio successfully to %s", output_path)
            return True
        except Exception as e:
            logger.error("Failed to synthesize TTS audio: %s", e)
            return False
