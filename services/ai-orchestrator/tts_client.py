"""
File: services/ai-orchestrator/tts_client.py
Layer: Worker — Text-to-Speech Client
Purpose: Loads Piper voice models and synthesizes commentary text into WAV files.
         CommentaryEngine uses it after selecting LLM or template commentary text.
Dependencies: PiperVoice, httpx model downloads, wave file writer, local models dir.
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
    """
    Piper TTS wrapper that handles model download, loading, and WAV synthesis.

    Attributes:
        models_dir (str): Directory containing Piper model and config files.
        model_path (str): Path to the ONNX voice model.
        config_path (str): Path to the Piper voice config JSON.
        _voice (Optional[PiperVoice]): Loaded Piper voice instance.
        _initialized (bool): Whether the voice is ready for synthesis.
    """

    def __init__(self, models_dir: str = None):
        if not models_dir:
            models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        self.models_dir = models_dir
        self.model_path = os.path.join(self.models_dir, f"{DEFAULT_MODEL_NAME}.onnx")
        self.config_path = os.path.join(self.models_dir, f"{DEFAULT_MODEL_NAME}.onnx.json")
        self._voice: Optional[PiperVoice] = None
        self._initialized = False

    async def initialize(self) -> bool:
        """
        Downloads missing Piper assets and loads the voice model.

        Returns:
            bool: True when the voice is initialized and ready for synthesis.

        Side Effects:
            Creates the models directory, downloads model files if absent, and
            loads the Piper model in an executor thread.
        """
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
                        # Hugging Face model links redirect to signed file URLs.
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
        """
        Synthesizes commentary text into a WAV file.

        Args:
            text (str): Commentary text to speak.
            output_path (str): Destination WAV path.

        Returns:
            bool: True when the WAV file was written successfully.

        Side Effects:
            Initializes the model if needed, creates output directories, and writes
            an audio file to disk.
        """
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

            # Piper synthesis is CPU-bound, so keep it off the main event loop.
            await loop.run_in_executor(None, run_synthesis)
            logger.info("Synthesized audio successfully to %s", output_path)
            return True
        except Exception as e:
            logger.error("Failed to synthesize TTS audio: %s", e)
            return False
