import { Activity, Cpu, CircuitBoard, FileJson, Search } from 'lucide-react';
import { TranscriptionStatus, PipelineStage } from '../api/types';
import './LiveStatusBanner.css';

interface LiveStatusBannerProps {
    status: TranscriptionStatus;
}

export function LiveStatusBanner({ status }: LiveStatusBannerProps) {
    if (!status.is_running && !status.pipeline?.is_running) return null;

    const pipeline = status.pipeline;

    const renderStage = (stage: PipelineStage | undefined, icon: any, label: string) => {
        if (!stage || (!stage.active && stage.completed === 0)) return null;

        const progress = stage.total > 0 ? (stage.completed / stage.total) * 100 : 0;
        const Icon = icon;
        const isActive = stage.active;

        return (
            <div className={`pipeline-stage ${isActive ? 'active' : 'completed'}`}>
                <div className="stage-info">
                    <div className="stage-header">
                        <Icon size={14} className={isActive ? 'spin-slow' : ''} />
                        <span className="stage-label">{label}</span>
                    </div>
                    <div className="stage-stats">
                        {stage.completed}/{stage.total}
                    </div>
                </div>
                <div className="stage-progress-bg">
                    <div
                        className="stage-progress-fill"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>
        );
    };

    return (
        <div className="status-banner">
            <div className="status-content">
                <div className="status-top">
                    <div className="status-left">
                        <div className="status-icon-wrapper">
                            <Activity className="spin text-yellow-400" size={24} />
                        </div>
                        <div className="status-text">
                            <div className="status-label">Pipeline Progress</div>
                            <div className="status-detail">
                                {status.current_episode || 'Processing multiple episodes...'}
                            </div>
                        </div>
                    </div>

                    <div className="status-right">
                        {status.vram_total_gb > 0 && (
                            <div className="metric-chip">
                                <CircuitBoard size={14} className="text-green-400" />
                                <span>{status.vram_used_gb?.toFixed(1)} / {status.vram_total_gb?.toFixed(0)} GB</span>
                            </div>
                        )}
                    </div>
                </div>

                <div className="pipeline-grid">
                    {renderStage(pipeline?.stages.transcription, Cpu, 'Transcribing')}
                    {renderStage(pipeline?.stages.summarization, FileJson, 'Summarizing')}
                    {renderStage(pipeline?.stages.rag, Search, 'Indexing')}
                </div>
            </div>
        </div>
    );
}
