/**
 * @file apps/dashboard/src/components/ProductionStatus.tsx
 * @layer Frontend — System Status UI
 * @description Displays high-level readiness for camera, radar, audio, graphics,
 *              and commentary production services.
 * @dependencies React
 */

import React from 'react';

/** Props for hardware and service status indicators. */
type Props = {
  liveCameraOk: boolean;
  radarOk: boolean;
  audioOk: boolean;
  graphicsOk: boolean;
  commentaryOk: boolean;
};

/**
 * Renders service/hardware readiness indicators for the operator.
 *
 * @param props - Boolean health flags for production dependencies
 * @returns React production status card
 */
export const ProductionStatus: React.FC<Props> = ({
  liveCameraOk,
  radarOk,
  audioOk,
  graphicsOk,
  commentaryOk,
}) => {
  return (
    <div className="card production-status-card">
      <h3>Edge Hardware & Services</h3>
      <div className="status-grid-hardware">
        <div className={`hardware-item ${liveCameraOk ? 'ok' : 'err'}`}>
          <span className="dot" />
          <div className="label-col">
            <span className="name">RTSP Camera</span>
            <span className="desc">{liveCameraOk ? "Active (1080p@30fps)" : "Offline"}</span>
          </div>
        </div>

        <div className={`hardware-item ${radarOk ? 'ok' : 'err'}`}>
          <span className="dot" />
          <div className="label-col">
            <span className="name">Radar Sensor</span>
            <span className="desc">{radarOk ? "Connected (SDR 24GHz)" : "Simulated"}</span>
          </div>
        </div>

        <div className={`hardware-item ${audioOk ? 'ok' : 'err'}`}>
          <span className="dot" />
          <div className="label-col">
            <span className="name">PA System</span>
            <span className="desc">{audioOk ? "Ready (Web Audio API)" : "Disconnected"}</span>
          </div>
        </div>

        <div className={`hardware-item ${graphicsOk ? 'ok' : 'err'}`}>
          <span className="dot" />
          <div className="label-col">
            <span className="name">Scoreboard GFX</span>
            <span className="desc">{graphicsOk ? "Ready (HTML Overlay)" : "Error"}</span>
          </div>
        </div>

        <div className={`hardware-item ${commentaryOk ? 'ok' : 'err'}`}>
          <span className="dot" />
          <div className="label-col">
            <span className="name">AI Commentary</span>
            <span className="desc">{commentaryOk ? "Online (Ollama Local)" : "Template Fallback"}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
