import { Activity, Cpu, CircuitBoard } from 'lucide-react';
import { TranscriptionStatus } from '../api/types';
import './LiveStatusBanner.css';

interface LiveStatusBannerProps {
    status: TranscriptionStatus;
}

export function LiveStatusBanner({ status }: LiveStatusBannerProps) {
    if (!status.is_running) return null;

    return (
        <div className="status-banner">
            <div className="status-content">
                <div className="status-left">
                    <div className="status-icon-wrapper">
                        <Activity className="spin text-yellow-400" size={24} />
                    </div>
                    <div className="status-text">
                        <div className="status-label">Transcribing Now</div>
                        <div className="status-detail">
                            {status.current_episode || 'Initializing...'}
                        </div>
                    </div>
                </div>

                <div className="status-right">
                    <div className="metric-chip">
                        <Cpu size={14} className="text-blue-400" />
                        <span>Stage: {status.stage}</span>
                    </div>
                    <div className="metric-chip">
                        <CircuitBoard size={14} className="text-green-400" />
                        <span>VRAM: {status.vram_used_gb?.toFixed(1) || 0}GB</span>
                    </div>
                    <div className="progress-pill">
                        {Math.round(status.progress)}%
                    </div>
                </div>
            </div>

            <div className="progress-bar-bg">
                <div
                    className="progress-bar-fill"
                    style={{ width: `${status.progress}%` }}
                />
            </div>
        </div>
    );
}
