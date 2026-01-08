import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { transcriptionApi } from '../api';
import type { TranscriptionStats, TranscriptionStatus } from '../api/types';
import { RefreshCw, Trash2, Square } from 'lucide-react';
import { BatchProgress } from '../components/BatchProgress';
import './DashboardPage.css';

function DashboardPage() {
    const navigate = useNavigate();
    const [stats, setStats] = useState<TranscriptionStats | null>(null);
    const [status, setStatus] = useState<TranscriptionStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isClearing, setIsClearing] = useState(false);
    const [isStopping, setIsStopping] = useState(false);

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

    const handleStopTranscription = async () => {
        if (!window.confirm('Are you sure you want to stop processing? This will immediately clear the queue and reset the pipeline.')) {
            return;
        }

        setIsStopping(true);
        try {
            await transcriptionApi.stopTranscription();
            // Full refresh to ensure we go back to idle
            await loadData();
        } catch (err) {
            console.error('Failed to stop transcription:', err);
            alert('Failed to stop transcription');
        } finally {
            setIsStopping(false);
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
                <div className="stat-card" onClick={() => navigate('/feeds')}>
                    <div className="stat-header">
                        <div className="stat-icon-bg"><span className="stat-icon">📡</span></div>
                        <div className="stat-label">Active Feeds</div>
                    </div>
                    <div className="stat-value">{stats?.active_feeds ?? 0}</div>
                    <div className="stat-sublabel">of {stats?.total_feeds ?? 0} total</div>
                </div>

                <div className="stat-card" onClick={() => navigate('/library')}>
                    <div className="stat-header">
                        <div className="stat-icon-bg"><span className="stat-icon">🎙️</span></div>
                        <div className="stat-label">Podcasts</div>
                    </div>
                    <div className="stat-value">{stats?.total_podcasts ?? 0}</div>
                    <div className="stat-sublabel">with transcripts</div>
                </div>

                <div className="stat-card" onClick={() => navigate('/library')}>
                    <div className="stat-header">
                        <div className="stat-icon-bg"><span className="stat-icon">📝</span></div>
                        <div className="stat-label">Processed</div>
                    </div>
                    <div className="stat-value">{stats?.total_episodes_processed ?? 0}</div>
                    <div className="stat-sublabel">all time</div>
                </div>

                <div className="stat-card highlight" onClick={() => navigate('/inbox')} style={{ borderColor: (stats?.selected_episodes ?? 0) > 0 ? 'var(--color-accent-primary)' : '' }}>
                    <div className="stat-header">
                        <div className="stat-icon-bg"><span className="stat-icon">⌛</span></div>
                        <div className="stat-label">Selected</div>
                    </div>
                    <div className="stat-value">{stats?.selected_episodes ?? 0}</div>
                    <div className="stat-sublabel">in inbox queue</div>
                </div>
            </div>

            {/* Unified Batch & System Progress */}
            <BatchProgress
                batchId={status?.current_batch_id || null}
                status={status}
                isInline={true}
            />

            {/* Run Transcription Section */}
            <div className="run-section glass-panel">
                <div className="section-header">
                    <h2>Ready to Transcribe?</h2>
                    <p>Process your selected episodes through the Whisper & Ollama pipeline</p>
                </div>

                <div className="run-controls">
                    <div className="run-controls-main">
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

                        {status?.is_running && (
                            <button
                                className="btn-secondary-lg stop-btn"
                                onClick={handleStopTranscription}
                                disabled={isStopping}
                            >
                                <Square size={18} fill="currentColor" />
                                Stop Processing
                            </button>
                        )}
                    </div>

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
