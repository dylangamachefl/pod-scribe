import React, { useState, useEffect } from 'react';
import { transcriptionApi, BatchProgressResponse } from '../api';
import { Cpu, FileText, Search, CheckCircle2, AlertCircle, Loader2, X } from 'lucide-react';
import './BatchProgress.css';

interface BatchProgressProps {
    batchId: string;
    onClose?: () => void;
    isInline?: boolean;
}

export const BatchProgress: React.FC<BatchProgressProps> = ({ batchId, onClose, isInline = false }) => {
    const [progress, setProgress] = useState<BatchProgressResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchProgress = async () => {
            try {
                // If we have data and it's completed, stop polling eventually?
                // For now, keep polling to show updates until dismissed or replaced
                const data = await transcriptionApi.getBatchProgress(batchId);
                setProgress(data);
                setError(null);
            } catch (err) {
                console.error('Failed to fetch batch progress:', err);
                // If 404, it might mean the batch hasn't registered yet or was cleared
                setError('Waiting for batch updates...');
            } finally {
                setLoading(false);
            }
        };

        fetchProgress();
        const interval = setInterval(fetchProgress, 2000);
        return () => clearInterval(interval);
    }, [batchId]);

    const renderPhase = (
        icon: React.ReactNode,
        label: string,
        count: number,
        total: number,
        isActive: boolean
    ) => {
        const isCompleted = count === total && total > 0;

        return (
            <div className={`pipeline-phase ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}>
                <div className="phase-icon">
                    {isCompleted ? <CheckCircle2 size={24} /> : icon}
                </div>
                <div className="phase-label">{label}</div>
                <div className="phase-count">{count} / {total}</div>
            </div>
        );
    };

    const getStatusClass = (status: string) => {
        const s = status.toLowerCase();
        if (s.includes('transcribing')) return 'transcribing';
        if (s.includes('summarizing')) return 'summarizing';
        if (s.includes('indexing')) return 'indexing';
        if (s === 'completed') return 'completed';
        if (s === 'failed') return 'failed';
        if (s === 'queued') return 'queued';
        return 'pending';
    };

    if (loading && !progress) {
        return (
            <div className="batch-progress-overlay">
                <div className="batch-progress-container">
                    <div className="batch-progress-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '200px' }}>
                        <Loader2 className="spin" size={32} />
                        <span style={{ marginLeft: '12px' }}>Loading batch progress...</span>
                    </div>
                </div>
            </div>
        );
    }

    const content = (
        <div className={`batch-progress-container ${isInline ? 'inline' : ''}`}>
            <div className="batch-progress-header">
                <div className="batch-title-group">
                    <h2>Batch Processing</h2>
                    <div className="batch-subtitle">ID: {batchId} • Last updated {progress ? new Date(progress.updated_at).toLocaleTimeString() : '...'}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    {progress && (
                        <div className={`batch-status-badge ${progress.status}`}>
                            {progress.status}
                        </div>
                    )}
                    {onClose && (
                        <button className="btn-icon" onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--color-text-tertiary)', cursor: 'pointer' }}>
                            <X size={24} />
                        </button>
                    )}
                </div>
            </div>

            <div className="batch-progress-body">
                {error && !progress ? (
                    <div className="error-state" style={{ textAlign: 'center', padding: '40px' }}>
                        <AlertCircle size={48} color="#ef4444" style={{ marginBottom: '16px' }} />
                        <p>{error}</p>
                    </div>
                ) : progress && (
                    <>
                        <div className="pipeline-overview">
                            {renderPhase(
                                <Cpu size={24} />,
                                'Transcribing',
                                progress.transcribed_count,
                                progress.total_episodes,
                                progress.transcribed_count < progress.total_episodes && progress.status === 'processing'
                            )}
                            {renderPhase(
                                <FileText size={24} />,
                                'Summarizing',
                                progress.summarized_count,
                                progress.total_episodes,
                                progress.summarized_count < progress.transcribed_count
                            )}
                            {renderPhase(
                                <Search size={24} />,
                                'Indexing',
                                progress.indexed_count,
                                progress.total_episodes,
                                progress.indexed_count < progress.summarized_count
                            )}
                        </div>

                        <div className="episode-list-header" style={{ marginBottom: '16px', fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
                            Episodes ({progress.episodes.length})
                        </div>

                        <div className="episode-progress-list">
                            {progress.episodes.map(ep => (
                                <div key={ep.id} className="episode-progress-item">
                                    <div className="ep-info">
                                        <div className="ep-title">{ep.title}</div>
                                        <div className="ep-status-text">
                                            <span className={`status-dot ${getStatusClass(ep.status)}`}></span>
                                            {ep.status}
                                        </div>
                                    </div>
                                    {ep.status === 'COMPLETED' && <CheckCircle2 size={18} color="#10b981" />}
                                    {ep.status === 'FAILED' && <AlertCircle size={18} color="#ef4444" />}
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>

            {!isInline && onClose && (
                <div className="batch-progress-footer">
                    <button className="btn-dismiss" onClick={onClose}>
                        Dismiss
                    </button>
                </div>
            )}
        </div>
    );

    if (isInline) {
        return content;
    }

    return (
        <div className="batch-progress-overlay">
            {content}
        </div>
    );
};
