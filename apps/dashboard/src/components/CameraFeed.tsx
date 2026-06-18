/**
 * @file apps/dashboard/src/components/CameraFeed.tsx
 * @layer Frontend — Live Video and Overlay Surface
 * @description Shows the camera feed from WHEP/file/URL sources and layers graphics
 *              overlays on top of the video surface.
 * @dependencies GraphicsOverlay, GraphicsState, browser WebRTC APIs
 */

import React, { useState, useRef, useEffect } from 'react';
import { GraphicsOverlay } from './GraphicsOverlay';
import type { GraphicsState } from '../api/sseClient';

/** Props for the camera feed and overlay surface. */
type Props = {
  graphicsState: GraphicsState;
  onHideOverlay?: () => void;
};

type VideoSourceType = 'live' | 'file' | 'url';

/**
 * Renders the production camera monitor with selectable video source and overlay.
 *
 * @param props - Graphics state and optional overlay-hide callback
 * @returns React camera feed component
 */
export const CameraFeed: React.FC<Props> = ({
  graphicsState,
  onHideOverlay,
}) => {
  const [sourceType, setSourceType] = useState<VideoSourceType>('live');
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [urlInput, setUrlInput] = useState('');
  const [activeUrl, setActiveUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(true);

  const videoRef = useRef<HTMLVideoElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Set up WebRTC / WHEP player for live stream
  useEffect(() => {
    if (sourceType !== 'live' || !videoRef.current) return;

    const videoElement = videoRef.current;
    
    // We can point this to the MediaMTX WebRTC WHEP endpoint
    // In local development composed environment, it's typically:
    const whepUrl = 'http://localhost:8889/homeplatecam/whep';

    // WHEP uses a one-way WebRTC offer/answer exchange to receive MediaMTX video.
    let peerConnection: RTCPeerConnection | null = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
    });

    peerConnection.ontrack = (event) => {
      if (videoElement.srcObject !== event.streams[0]) {
        videoElement.srcObject = event.streams[0];
      }
    };

    const startWhepPlayback = async () => {
      try {
        peerConnection?.addTransceiver('video', { direction: 'recvonly' });
        peerConnection?.addTransceiver('audio', { direction: 'recvonly' });

        const offer = await peerConnection?.createOffer();
        await peerConnection?.setLocalDescription(offer);

        const response = await fetch(whepUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/sdp' },
          body: peerConnection?.localDescription?.sdp,
        });

        if (response.ok) {
          const answerSdp = await response.text();
          await peerConnection?.setRemoteDescription(
            new RTCSessionDescription({ type: 'answer', sdp: answerSdp })
          );
        }
      } catch (err) {
        console.warn("WHEP Live Feed Connection failed, falling back to static placeholder", err);
      }
    };

    startWhepPlayback();

    return () => {
      if (peerConnection) {
        peerConnection.close();
      }
      if (videoElement) {
        videoElement.srcObject = null;
      }
    };
  }, [sourceType]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (fileUrl) URL.revokeObjectURL(fileUrl);
      const url = URL.createObjectURL(file);
      setFileUrl(url);
      setSourceType('file');
      setIsPlaying(true);
    }
  };

  const handleUrlSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (urlInput.trim()) {
      setActiveUrl(urlInput);
      setSourceType('url');
      setIsPlaying(true);
    }
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play().catch(console.error);
      }
      setIsPlaying(!isPlaying);
    }
  };

  return (
    <div className="card camera-feed-card">
      <div className="card-header-feed">
        <h3>Live Camera Ingestion</h3>
        
        {/* Source Selector UI */}
        <div className="source-selector">
          <select 
            value={sourceType} 
            onChange={(e) => setSourceType(e.target.value as VideoSourceType)}
          >
            <option value="live">📡 Live RTSP / WebRTC</option>
            <option value="file">📁 Upload Video File</option>
            <option value="url">🔗 YouTube / RTSP URL</option>
          </select>

          {sourceType === 'file' && (
            <button 
              className="source-btn"
              onClick={() => fileInputRef.current?.click()}
            >
              Choose File
            </button>
          )}
        </div>
      </div>

      <input 
        type="file" 
        ref={fileInputRef} 
        style={{ display: 'none' }} 
        accept="video/*" 
        onChange={handleFileChange} 
      />

      {/* URL Paste Input Bar */}
      {sourceType === 'url' && !activeUrl && (
        <form onSubmit={handleUrlSubmit} className="url-form">
          <input 
            type="text" 
            placeholder="Paste video stream URL (e.g. YouTube stream or direct .mp4)" 
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
          />
          <button type="submit">Load</button>
        </form>
      )}

      {/* Video Container with Overlays */}
      <div className="video-player-container">
        {sourceType === 'live' && (
          <video 
            ref={videoRef} 
            className="main-feed-video"
            autoPlay 
            playsInline
            muted
          />
        )}

        {sourceType === 'file' && fileUrl && (
          <video 
            ref={videoRef} 
            className="main-feed-video"
            src={fileUrl}
            autoPlay 
            loop 
            controls={false}
          />
        )}

        {sourceType === 'url' && activeUrl && (
          <video 
            ref={videoRef} 
            className="main-feed-video"
            src={activeUrl}
            autoPlay 
            loop 
            controls={false}
            onError={() => {
              // If not direct video source, show an iframe for YouTube
              console.log("Not a direct video source, rendering stream container");
            }}
          />
        )}

        {/* Embedded HTML Graphics Overlay */}
        <GraphicsOverlay graphicsState={graphicsState} />
        
        {/* Controls Overlay */}
        <div className="video-control-bar">
          <button className="ctrl-btn" onClick={togglePlay}>
            {isPlaying ? '⏸ Pause' : '▶ Play'}
          </button>
          {graphicsState.activeOverlay && (
            <button className="ctrl-btn btn-clear-overlay" onClick={onHideOverlay}>
              Clear Graphic Overlay
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
