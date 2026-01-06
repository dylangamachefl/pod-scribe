import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { transcriptionApi } from '../api';
import type { TranscriptionStats, TranscriptionStatus } from '../api/types';
import { RefreshCw, Trash2 } from 'lucide-react';
import './DashboardPage.css';

function DashboardPage() {
    const navigate = useNavigate();
    const [stats, setStats] = useState<TranscriptionStats | null>(null);
    const [status, setStatus] = useState<TranscriptionStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isClearing, setIsClearing] = useState(false);

    const loadData = async () => {
        try {
            const [statsData, statusData] = await Promise.all([
                transcriptionApi.getStats(),
                transcriptionApi.getTranscriptionStatus(),
            ]);
            setStats(statsData);
            setStatus(statusData);
            setError(null);
        } catch (err) {
            setError('Failed to load dashboard data');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();

        // Always poll, but frequency depends on if transcription is running
        const getInterval = () => (status?.is_running ? 2000 : 10000);

        const interval = setInterval(() => {
            loadData();
        }, getInterval());

        return () => clearInterval(interval);
    }, [status?.is_running]);

    const handleStartTranscription = async () => {
        try {
            await transcriptionApi.startTranscription();
            loadData(); // Refresh after starting
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to start transcription');
        }
    };

    const handleClearStatus = async () => {
        if (!window.confirm('Are you sure you want to clear all pipeline status? This will reset the UI even if backend tasks are still running.')) {
            return;
        }

        setIsClearing(true);
        try {
            await transcriptionApi.clearTranscriptionStatus();
            await loadData();
        } catch (err) {
            console.error('Failed to clear status:', err);
            alert('Failed to clear status');
        } finally {
            setIsClearing(false);
        }
    };

    if (loading) {
        return (
            <div className="dashboard-page">
                <div className="loading">Loading dashboard...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="dashboard-page">
                <div className="header-actions">
                    <button className="btn-icon" onClick={loadData} title="Retry">
                        <RefreshCw size={20} />
                    </button>
                </div>
                <div className="error">{error}</div>
            </div>
        );
    }

    return (
        <div className="dashboard-page">
            <header className="dashboard-header">
                <div className="header-main">
                    <h1>Dashboard</h1>
                    <p>Overview of your podcast transcription activity</p>
                </div>
                <div className="header-actions">
                    <button
                        className={`btn-icon cleanup ${isClearing ? 'spinning' : ''}`}
                        onClick={handleClearStatus}
                        disabled={isClearing}
                        title="Clear Stale Status"
                    >
                        <Trash2 size={18} />
                    </button>
                    <button className="btn-icon" onClick={loadData} title="Refresh">
                        <RefreshCw size={18} className={loading ? 'spinning' : ''} />
                    </button>
                </div>
            </header>

            {/* Statistics Cards */}
            <div className="stats-grid">
                <div className="stat-card" onClick={() => navigate('/feeds')} style={{ cursor: 'pointer' }}>
                    <div className="stat-icon">📡</div>
                    <div className="stat-content">
                        <div className="stat-label">Active Feeds</div>
                        <div className="stat-value">{stats?.active_feeds ?? 0}</div>
                        <div className="stat-sublabel">of {stats?.total_feeds ?? 0} total</div>
                    </div>
                </div>

                <div className="stat-card" onClick={() => navigate('/library')} style={{ cursor: 'pointer' }}>
                    <div className="stat-icon">🎙️</div>
                    <div className="stat-content">
                        <div className="stat-label">Podcasts</div>
                        <div className="stat-value">{stats?.total_podcasts ?? 0}</div>
                        <div className="stat-sublabel">with transcripts</div>
                    </div>
                </div>

                <div className="stat-card" onClick={() => navigate('/library')} style={{ cursor: 'pointer' }}>
                    <div className="stat-icon">📝</div>
                    <div className="stat-content">
                        <div className="stat-label">Processed</div>
                        <div className="stat-value">{stats?.total_episodes_processed ?? 0}</div>
                        <div className="stat-sublabel">all time</div>
                    </div>
                </div>

                <div className="stat-card" onClick={() => navigate('/inbox')} style={{ cursor: 'pointer', borderColor: (stats?.selected_episodes ?? 0) > 0 ? 'var(--color-accent-primary)' : '' }}>
                    <div className="stat-icon">⌛</div>
                    <div className="stat-content">
                        <div className="stat-label">Selected</div>
                        <div className="stat-value">{stats?.selected_episodes ?? 0}</div>
                        <div className="stat-sublabel">in inbox queue</div>
                    </div>
                </div>
            </div>

            {/* Pipeline Overview */}
            <div className="status-grid" style={{ marginBottom: '40px' }}>
                {/* GPU Status */}
                <div className="status-card">
                    <h3>System Resources</h3>
                    <div className="gpu-info">
                        <div className="metric">
                            <span className="metric-label">GPU</span>
                            <span className="metric-value">{status?.gpu_name && status.gpu_name !== 'Unknown' ? status.gpu_name : 'No GPU Detected'}</span>
                        </div>
                        <div className="metric">
                            <span className="metric-label">Utilization</span>
                            <span className="metric-value">{status?.gpu_usage ?? 0}%</span>
                        </div>
                        <div className="progress-bar">
                            <div
                                className="progress-fill gpu"
                                style={{ width: `${status?.gpu_usage ?? 0}%` }}
                            />
                        </div>
                        {status && status.vram_total_gb > 0 ? (
                            <>
                                <div className="metric">
                                    <span className="metric-label">VRAM Usage</span>
                                    <span className="metric-value">
                                        {status.vram_used_gb.toFixed(1)} /{' '}
                                        {status.vram_total_gb.toFixed(1)} GB
                                    </span>
                                </div>
                                <div className="progress-bar">
                                    <div
                                        className="progress-fill vram"
                                        style={{
                                            width: `${(status.vram_used_gb / status.vram_total_gb) * 100}%`,
                                        }}
                                    />
                                </div>
                            </>
                        ) : (
                            <div className="metric" style={{ opacity: 0.5 }}>
                                <span className="metric-label">VRAM Usage</span>
                                <span className="metric-value">N/A</span>
                            </div>
                        )}
                    </div>
                </div>

                {/* Batch Progress */}
                <div className="status-card">
                    <h3>Pipeline Sync</h3>
                    <div className="batch-info">
                        <div className="metric">
                            <span className="metric-label">Current Task</span>
                            <span className="metric-value" style={{ color: status?.is_running ? 'var(--color-accent-secondary)' : 'var(--color-text-tertiary)' }}>
                                {status?.is_running ? 'Processing Queue' : 'Idle'}
                            </span>
                        </div>
                        <div className="metric">
                            <span className="metric-label">Batch Progress</span>
                            <span className="metric-value">
                                {status?.episodes_completed ?? 0} / {status?.episodes_total ?? 0}
                            </span>
                        </div>
                        <div className="progress-bar">
                            <div
                                className="progress-fill batch"
                                style={{
                                    width:
                                        status && status.episodes_total > 0
                                            ? `${(status.episodes_completed / status.episodes_total) * 100}%`
                                            : '0%',
                                }}
                            />
                        </div>
                        <div className="progress-label">
                            {status && status.episodes_total > 0
                                ? `${Math.round((status.episodes_completed / status.episodes_total) * 100)}% complete`
                                : 'Ready'}
                        </div>
                    </div>
                </div>
            </div>


            {/* Processing Queue */}
            {status?.active_episodes && status.active_episodes.length > 0 && (
                <div className="processing-queue">
                    <h2><span style={{ fontSize: '1.2rem' }}>⚡</span> Active Processing ({status.active_episodes.length})</h2>
                    <div className="queue-grid">
                        {status.active_episodes.map((ep) => (
                            <div key={ep.episode_id} className="queue-item">
                                <div className="queue-item-header">
                                    <div className="queue-item-info">
                                        <div className="queue-item-title">{ep.title}</div>
                                        <div className="queue-item-podcast">{ep.podcast}</div>
                                    </div>
                                    <div className="queue-item-stage">{ep.stage === 'unknown' ? 'Ready' : ep.stage}</div>
                                </div>

                                <div className="queue-item-pipeline">
                                    <div className={`pipeline-step ${ep.services?.transcription ? (ep.services.transcription.stage === 'saving' && ep.services.transcription.progress === 1.0 ? 'completed' : 'active') : ''}`} title="Transcription" />
                                    <div className={`pipeline-step ${ep.services?.summarization ? 'active' : (ep.services?.transcription?.progress === 1.0 ? (ep.services?.summarization ? 'active' : 'pending') : '')}`} title="Summarization" />
                                    <div className={`pipeline-step ${ep.services?.rag ? 'active' : ''}`} title="RAG Ingestion" />
                                </div>

                                <div className="progress-bar">
                                    <div
                                        className="progress-fill"
                                        style={{ width: `${Math.round((ep.progress ?? 0) * 100)}%` }}
                                    />
                                </div>

                                <div className="queue-item-progress">
                                    <span>{ep.stage === 'unknown' ? 'Initializing...' : ep.stage}</span>
                                    <span>{Math.round((ep.progress ?? 0) * 100)}%</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Run Transcription Section */}
            <div className="run-section">
                <h2>Ready to Transcribe?</h2>
                <p>Process your selected episodes through the Whisper & Ollama pipeline</p>

                <div className="run-controls">
                    <button
                        className="btn-primary-lg"
                        onClick={handleStartTranscription}
                        disabled={
                            status?.is_running || (stats?.selected_episodes || 0) === 0
                        }
                    >
                        {status?.is_running
                            ? 'Processing...'
                            : `🚀 Run Transcription (${stats?.selected_episodes ?? 0})`}
                    </button>

                    {(stats?.selected_episodes || 0) === 0 && !status?.is_running && (
                        <div className="warning clickable" onClick={() => navigate('/inbox')} style={{ cursor: 'pointer' }}>
                            <span>⚠️</span>
                            No episodes selected. Click here to go to your <strong>Inbox</strong> and select episodes to transcribe.
                        </div>
                    )}

                    {(stats?.selected_episodes || 0) > 0 && !status?.is_running && (
                        <div className="info">
                            <span>✅</span>
                            Ready to transcribe {stats?.selected_episodes} selected episode(s)
                        </div>
                    )}
                </div>
            </div>

            {/* Live Activity Feed */}
            <div className="live-activity-card">
                <div className="live-activity-header">
                    <h3>
                        <span className="pulse-dot"></span>
                        Live Activity
                    </h3>
                    <span className="live-activity-source">redis:transcription_queue</span>
                </div>
                <div className="live-activity-content">
                    {status?.recent_logs && status.recent_logs.length > 0 ? (
                        status.recent_logs.map((log, i) => (
                            <div key={i} className="log-entry">
                                <span className="log-prefix">{i === 0 ? '>' : ' '}</span>
                                {log}
                            </div>
                        ))
                    ) : (
                        <div className="log-entry" style={{ color: '#64748b' }}>
                            <span className="log-prefix">#</span>
                            Waiting for activity...
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default DashboardPage;
