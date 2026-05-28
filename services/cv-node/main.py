import asyncio
import logging
import os
import sys

# Setup path for local packages/contracts/python imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTRACTS_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "../../packages/contracts/python"))
sys.path.append(CONTRACTS_PATH)

try:
    from dugout.v1.cv_observation_pb2 import CvObservation
    contracts_available = True
except ImportError as e:
    logging.warning(f"Could not import generated contract types: {e}")
    contracts_available = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cv-node")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
CAMERA_RTSP_STREAM = os.getenv("CV_NODE_CAMERA_RTSP_STREAM", "rtsp://localhost:8554/home_plate_cam")

async def main():
    logger.info("Starting CV Edge Node...")
    logger.info(f"NATS target: {NATS_URL}")
    logger.info(f"Camera target: {CAMERA_RTSP_STREAM}")
    logger.info(f"Contracts loaded: {contracts_available}")

    # Future phase will implement GStreamer/FFmpeg/OpenCV RTSP ingestion here
    # and YOLO inference engine tracking loop.
    
    while True:
        # Idle/keep alive loop
        await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("CV Edge Node stopped by user.")
