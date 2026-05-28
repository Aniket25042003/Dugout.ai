import asyncio
import logging
import os
import sys
from fastapi import FastAPI

# Setup path for local packages/contracts/python imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTRACTS_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "../../packages/contracts/python"))
sys.path.append(CONTRACTS_PATH)

# Verify imports work
try:
    from dugout.v1.game_state_pb2 import GameState
    from dugout.v1.game_event_pb2 import GameEvent
    from dugout.v1.cv_observation_pb2 import CvObservation
    from dugout.v1.production_command_pb2 import ProductionCommand
    contracts_available = True
except ImportError as e:
    logging.warning(f"Could not import generated contract types: {e}")
    contracts_available = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai-orchestrator")

app = FastAPI(title="Dugout.ai AI Orchestrator")

# Configuration
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
DATABASE_URL = os.getenv("DATABASE_URL", "postgres://dugout_admin:dugout_secret@localhost:5432/dugout?sslmode=disable")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting AI Orchestrator...")
    logger.info(f"NATS target: {NATS_URL}")
    logger.info(f"Database target: {DATABASE_URL}")
    logger.info(f"Contracts path configured: {contracts_available} at {CONTRACTS_PATH}")
    
    # Placeholder for NATS JetStream setup
    # In future phases, we will start background listeners here

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Stopping AI Orchestrator...")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-orchestrator",
        "contracts_loaded": contracts_available
    }
