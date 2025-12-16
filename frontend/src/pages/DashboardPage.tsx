import { useState, useEffect } from 'react';
import { transcriptionApi } from '../api';
import type { TranscriptionStats, TranscriptionStatus } from '../api/types';
import './DashboardPage.css';

function DashboardPage() {
    const [stats, setStats] = useState<TranscriptionStats | null>(null);
    const [status, setStatus] = useState<TranscriptionStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

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

        // Auto-refresh if transcription is running
        const interval = setInterval(() => {
            if (status?.is_running) {
                loadData();
            }
        }, 2000); // Refresh every 2 seconds when running

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
                <div className="error">{error}</div>
            </div>
        );
    }

    const stageEmojis: Record<string, string> = {
        idle: '⏸️',
        preparing: '⚙️',
        downloading: '⬇️',
        transcribing: '🎤',
        diarizing: '👥',
        saving: '💾',
        processing: '🔄',
    };

    return (
        <div className="dashboard-page">
            <div className="dashboard-header">
                <h1>📊 Dashboard</h1>
                <p>Overview of your podcast transcription activity</p>
            </div>

            {/* Statistics Cards */}
            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-icon">📡</div>
                    <div className="stat-content">
                        <div className="stat-label">Active Feeds</div>
                        <div className="stat-value">{stats?.active_feeds || 0}</div>
                        <div className="stat-sublabel">of {stats?.total_feeds || 0} total</div>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon">🎙️</div>
                    <div className="stat-content">
                        <div className="stat-label">Podcasts</div>
                        <div className="stat-value">{stats?.total_podcasts || 0}</div>
                        <div className="stat-sublabel">with transcripts</div>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon">📝</div>
                    <div className="stat-content">
                        <div className="stat-label">Episodes Processed</div>
                        <div className="stat-value">{stats?.total_episodes_processed || 0}</div>
                        <div className="stat-sublabel">all time</div>
                    </div>
                </div>

                <div className="stat-card">
                    <div className="stat-icon">⏳</div>
                    <div className="stat-content">
                        <div className="stat-label">Selected Episodes</div>
                        <div className="stat-value">{stats?.selected_episodes || 0}</div>
                        <div className="stat-sublabel">of {stats?.pending_episodes || 0} pending</div>
                    </div>
                </div>
            </div>

            {/* Transcription Status */}
            {status?.is_running && (
                <div className="transcription-status">
                    <h2>🔴 Transcription In Progress</h2>

                    <div className="status-grid">
                        {/* Current Episode */}
                        <div className="status-card">
                            <h3>Current Episode</h3>
                            <div className="status-info">
                                <div className="status-stage">
                                    <span className="stage-emoji">
                                        {stageEmojis[status.stage] || '🔄'}
                                    </span>
                                    <span className="stage-name">{status.stage || 'Processing'}</span>
                                </div>
                                <div className="episode-name">{status.current_episode || 'Unknown'}</div>
                                <div className="podcast-name">{status.current_podcast || 'Unknown'}</div>
                            </div>
                            <div className="progress-bar">
                                <div
                                    className="progress-fill"
                                    style={{ width: `${(status.progress || 0) * 100}%` }}
                                />
                            </div>
                            <div className="progress-label">
                                Progress: {Math.round((status.progress || 0) * 100)}%
                            </div>
                        </div>

                        {/* GPU Status */}
                        <div className="status-card">
                            <h3>GPU Status</h3>
                            <div className="gpu-info">
                                <div className="gpu-name">{status.gpu_name || 'N/A'}</div>
                                <div className="metric">
                                    <span className="metric-label">GPU Utilization</span>
                                    <span className="metric-value">{status.gpu_usage}%</span>
                                </div>
                                <div className="progress-bar">
                                    <div
                                        className="progress-fill gpu"
                                        style={{ width: `${status.gpu_usage}%` }}
                                    />
                                </div>
                                {status.vram_total_gb > 0 && (
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
                                )}
                            </div>
                        </div>

                        {/* Batch Progress */}
                        <div className="status-card">
                            <h3>Batch Progress</h3>
                            <div className="batch-info">
                                <div className="metric">
                                    <span className="metric-label">Episodes Completed</span>
                                    <span className="metric-value">
                                        {status.episodes_completed} / {status.episodes_total}
                                    </span>
                                </div>
                                <div className="progress-bar">
                                    <div
                                        className="progress-fill batch"
                                        style={{
                                            width:
                                                status.episodes_total > 0
                                                    ? `${(status.episodes_completed / status.episodes_total) * 100}%`
                                                    : '0%',
                                        }}
                                    />
                                </div>
                                <div className="progress-label">
                                    {status.episodes_total > 0
                                        ? `${Math.round((status.episodes_completed / status.episodes_total) * 100)}% complete`
                                        : 'Waiting...'}
                                </div>
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
                                {status.recent_logs && status.recent_logs.length > 0 ? (
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
                </div>
            )}

            {/* Run Transcription */}
            <div className="run-section">
                <h2>▶️ Run Transcription</h2>
                <p>Process selected episodes from the queue</p>

                <div className="run-controls">
                    <button
                        className="btn-primary"
                        onClick={handleStartTranscription}
                        disabled={
                            status?.is_running || (stats?.selected_episodes || 0) === 0
                        }
                    >
                        {status?.is_running
                            ? '🔴 Transcription Running...'
                            : `🚀 Run Transcription (${stats?.selected_episodes || 0})`}
                    </button>

                    {(stats?.selected_episodes || 0) === 0 && !status?.is_running && (
                        <div className="warning">
                            ⚠️ No episodes selected. Go to Episode Queue to select episodes to
                            transcribe.
                        </div>
                    )}

                    {(stats?.selected_episodes || 0) > 0 && !status?.is_running && (
                        <div className="info">
                            ✅ Ready to transcribe {stats?.selected_episodes} selected episode(s)
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default DashboardPage;
