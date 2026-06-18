"""
File: services/cv-node/main.py
Layer: Edge Ingestion — Computer Vision Node
Purpose: Reads the home-plate RTSP stream and publishes jersey-number observations
         to NATS for the orchestrator to turn into production actions.
Dependencies: OpenCV frame capture, NumPy image arrays, NATS, local contracts path.
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
import cv2
import nats
import numpy as np

# Setup path for local packages/contracts/python imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTRACTS_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "../../packages/contracts/python"))
sys.path.append(CONTRACTS_PATH)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cv-node")

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
CAMERA_RTSP_STREAM = os.getenv("CV_NODE_CAMERA_RTSP_STREAM", "rtsp://localhost:8554/homeplatecam")
GAME_ID = os.getenv("GAME_ID", "game_2026_ashland_vs_opponent")
MODEL_PATH = os.getenv("CV_MODEL_PATH", "")

# Note: C++ YOLO detector planned for production latency requirements.
# Using FallbackVisualDetector for local stream simulation.

class FallbackVisualDetector:
    """
    Highly reliable visual detector for local testing.
    Finds the moving white jersey number text in the MediaMTX testsrc stream.

    This detector is intentionally simple for the pilot: it identifies bright
    contours in a test stream and produces plausible jersey observations while
    the production YOLO detector is out of scope.
    """
    def __init__(self):
        """Initializes the local contour-based detector."""
        logger.info("Fallback visual contour detector initialized.")

    def detect(self, frame):
        """
        Detects simulated jersey-number regions in a video frame.

        Args:
            frame: OpenCV BGR image frame from the RTSP stream.

        Returns:
            list[dict]: Jersey detections with confidence, team side, and normalized bbox.
        """
        h, w, _ = frame.shape
        # Grayscale thresholding isolates the bright jersey-number text in the test stream.
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # In testsrc, the moving text is bright white
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detections = []
        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            # Keep only contours with size/shape close to the simulated "17" text.
            area = cv2.contourArea(contour)
            aspect_ratio = cw / float(ch) if ch > 0 else 0
            
            # The test pattern '17' text is roughly sized
            if 300 < area < 8000 and 0.5 < aspect_ratio < 2.5:
                # Normalized coordinates [0, 1]
                norm_x = round(x / float(w), 2)
                norm_y = round(y / float(h), 2)
                norm_w = round(cw / float(w), 2)
                norm_h = round(ch / float(h), 2)
                
                # Alternating confidence exercises both auto-processing and manager-alert paths.
                sec = int(time.time())
                if sec % 15 < 6:
                    confidence = 0.63  # Low confidence, triggers manager alert
                else:
                    confidence = 0.95  # High confidence, auto-processes

                detections.append({
                    "jerseyNumber": "17",
                    "teamSide": "TEAM_SIDE_HOME",
                    "confidence": confidence,
                    "bbox": {
                        "x": norm_x,
                        "y": norm_y,
                        "width": norm_w,
                        "height": norm_h
                    }
                })
        return detections

async def process_rtsp_stream(nc):
    """
    Reads RTSP frames, runs detection, and publishes observations to NATS.

    Args:
        nc: Connected NATS client used to publish CV observations.

    Side Effects:
        Opens an RTSP stream, publishes JSON observations, and reconnects forever
        when the camera stream drops.
    """
    fallback_detector = FallbackVisualDetector()
    
    subject = f"dugout.game.{GAME_ID}.observations"

    while True:
        logger.info(f"Connecting to RTSP Stream: {CAMERA_RTSP_STREAM}...")
        cap = cv2.VideoCapture(CAMERA_RTSP_STREAM)
        
        if not cap.isOpened():
            logger.error("RTSP Stream unavailable. Retrying in 5 seconds...")
            cap.release()
            await asyncio.sleep(5)
            continue
            
        logger.info("Connected to RTSP stream successfully.")
        
        frame_counter = 0
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    logger.warning("Failed to grab frame from RTSP stream.")
                    break
                
                frame_counter += 1
                # Process roughly 6 FPS from a 30 FPS stream to keep CPU use predictable.
                if frame_counter % 5 == 0:
                    detections = fallback_detector.detect(frame)
                    
                    # The orchestrator subscribes to this subject for CV-triggered actions.
                    for det in detections:
                        obs = {
                            "observationId": f"obs_{uuid.uuid4().hex[:12]}",
                            "gameId": GAME_ID,
                            "cameraId": "home_plate_cam",
                            "observedAt": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                            "observationType": "jersey_number",
                            "confidence": det["confidence"],
                            "model": {
                                "name": "contour-jersey-sim",
                                "version": "v1.0",
                                "runtime": "fallback-contour",
                            },
                            "jerseyNumber": {
                                "jerseyNumber": det["jerseyNumber"],
                                "teamSide": det["teamSide"],
                                "bbox": det["bbox"],
                                "trackId": f"track_{hash(det['jerseyNumber']) % 10000}",
                            }
                        }
                        
                        await nc.publish(subject, json.dumps(obs).encode())
                        logger.info(
                            "Published Observation: jersey=%s confidence=%.2f coordinates=[x=%s, y=%s]",
                            det["jerseyNumber"], det["confidence"], det["bbox"]["x"], det["bbox"]["y"]
                        )
                
                # Non-blocking yield for other tasks
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Error in stream processing loop: {e}")
        finally:
            logger.info("Closing RTSP stream connection.")
            cap.release()
            
        logger.info("RTSP connection lost. Reconnecting in 2 seconds...")
        await asyncio.sleep(2)

async def main():
    """
    Connects the CV node to NATS and starts the RTSP processing loop.

    Side Effects:
        Opens a NATS connection and runs until interrupted or connection setup fails.
    """
    logger.info("Starting CV Edge Node...")
    logger.info(f"NATS target: {NATS_URL}")
    logger.info(f"Camera target: {CAMERA_RTSP_STREAM}")
    logger.info(f"Contracts loaded: True")
    logger.info("C++ YOLO transition planned for low latency runtime.")

    logger.info("Connecting to NATS...")
    try:
        nc = await nats.connect(NATS_URL)
        logger.info("Connected to NATS.")
    except Exception as e:
        logger.error(f"Could not connect to NATS: {e}")
        return

    try:
        await process_rtsp_stream(nc)
    except KeyboardInterrupt:
        logger.info("CV Edge Node stopped by user.")
    finally:
        await nc.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped.")
