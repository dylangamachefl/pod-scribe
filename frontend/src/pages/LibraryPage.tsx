import { useState, useEffect } from 'react';
import './LibraryPage.css';
import { api, Summary } from '../api';
import EpisodeDetailModal from '../components/EpisodeDetailModal';
import ChatPopup from '../components/ChatPopup';

function LibraryPage() {
    const [summaries, setSummaries] = useState<Summary[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedEpisode, setSelectedEpisode] = useState<Summary | null>(null);
    const [chatEpisode, setChatEpisode] = useState<Summary | null>(null);

    useEffect(() => {
        loadSummaries();
    }, []);

    const loadSummaries = async () => {
        try {
            setIsLoading(true);
            const data = await api.getSummaries();
            setSummaries(data);
        } catch (err) {
            console.error('Error loading summaries:', err);
            setError('Failed to load summaries');
        } finally {
            setIsLoading(false);
        }
    };

    const handleEpisodeClick = (summary: Summary) => {
        setSelectedEpisode(summary);
    };

    const handleOpenChat = (episode: Summary) => {
        setChatEpisode(episode);
        setSelectedEpisode(null); // Close modal when opening chat
    };

    if (isLoading) {
        return (
            <div className="library-page">
                <div className="loading-state">
                    <div className="loading-spinner"></div>
                    <p>Loading your podcast library...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="library-page">
                <div className="error-state">
                    <div className="error-icon">⚠️</div>
                    <h3>Error Loading Library</h3>
                    <p>{error}</p>
                    <button className="btn-primary" onClick={loadSummaries}>
                        Try Again
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="library-page">
            <div className="library-header">
                <h1>📚 Podcast Library</h1>
                <p className="subtitle">{summaries.length} episodes indexed</p>
            </div>

            <div className="summaries-grid">
                {summaries.map((summary, idx) => (
                    <div
                        key={idx}
                        className="summary-card glass clickable"
                        onClick={() => handleEpisodeClick(summary)}
                    >
                        <div className="card-header">
                            <div className="podcast-badge">{summary.podcast_name}</div>
                            <div className="duration">{summary.duration || 'N/A'}</div>
                        </div>

                        <h3 className="episode-title">{summary.episode_title}</h3>

                        <div className="summary-text">{summary.summary}</div>

                        {summary.key_topics.length > 0 && (
                            <div className="topics">
                                <div className="topics-label">Key Topics:</div>
                                <div className="topic-tags">
                                    {summary.key_topics.slice(0, 3).map((topic, i) => (
                                        <span key={i} className="topic-tag">{topic}</span>
                                    ))}
                                    {summary.key_topics.length > 3 && (
                                        <span className="topic-tag more">+{summary.key_topics.length - 3} more</span>
                                    )}
                                </div>
                            </div>
                        )}

                        <div className="card-footer">
                            <div className="speakers">
                                👥 {summary.speakers.join(', ')}
                            </div>
                            <div className="created-date">{summary.created_at}</div>
                        </div>
                    </div>
                ))}
            </div>

            {summaries.length === 0 && (
                <div className="empty-state">
                    <div className="empty-icon">📭</div>
                    <h3>No episodes yet</h3>
                    <p>Transcribe some podcast episodes to see them here!</p>
                </div>
            )}

            {selectedEpisode && (
                <EpisodeDetailModal
                    episode={selectedEpisode}
                    onClose={() => setSelectedEpisode(null)}
                    onOpenChat={() => handleOpenChat(selectedEpisode)}
                />
            )}

            {chatEpisode && (
                <ChatPopup
                    episode={chatEpisode}
                    onClose={() => setChatEpisode(null)}
                />
            )}
        </div>
    );
}

export default LibraryPage;
