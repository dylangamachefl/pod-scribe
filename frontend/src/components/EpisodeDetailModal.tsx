import { useState } from 'react';
import './EpisodeDetailModal.css';
import { Summary } from '../api/types';
import { transcriptionApi } from '../api';

interface EpisodeDetailModalProps {
    episode: Summary;
    onClose: () => void;
    onOpenChat: () => void;
}

function EpisodeDetailModal({ episode, onClose, onOpenChat }: EpisodeDetailModalProps) {
    const [showTranscript, setShowTranscript] = useState(false);
    const [transcript, setTranscript] = useState<string | null>(null);
    const [loadingTranscript, setLoadingTranscript] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');

    const loadTranscript = async () => {
        if (transcript) {
            setShowTranscript(!showTranscript);
            return;
        }

        try {
            setLoadingTranscript(true);
            const data = await transcriptionApi.getTranscript(
                episode.podcast_name,
                episode.episode_title
            );
            setTranscript(data.content);
            setShowTranscript(true);
        } catch (err) {
            console.error('Failed to load transcript:', err);
            alert('Failed to load transcript');
        } finally {
            setLoadingTranscript(false);
        }
    };

    const downloadTranscript = async () => {
        try {
            const data = await transcriptionApi.getTranscript(
                episode.podcast_name,
                episode.episode_title
            );
            const blob = new Blob([data.content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${episode.episode_title}.txt`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            console.error('Download failed:', err);
            alert('Failed to download transcript');
        }
    };

    const downloadSummary = () => {
        const summaryContent = `${episode.episode_title}\n${episode.podcast_name}\n\n${episode.summary}\n\nKey Topics:\n${episode.key_topics.map(t => `- ${t}`).join('\n')}\n\nSpeakers: ${episode.speakers.join(', ')}`;
        const blob = new Blob([summaryContent], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${episode.episode_title} - Summary.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const highlightText = (text: string) => {
        if (!searchTerm || !transcript) return text;
        const parts = text.split(new RegExp(`(${searchTerm})`, 'gi'));
        return parts.map((part, index) =>
            part.toLowerCase() === searchTerm.toLowerCase() ? (
                <mark key={index}>{part}</mark>
            ) : (
                part
            )
        );
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content glass" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <div>
                        <div className="podcast-badge">{episode.podcast_name}</div>
                        <h2>{episode.episode_title}</h2>
                        <div className="episode-meta">
                            {episode.duration && <span>⏱️ {episode.duration}</span>}
                            <span>📅 {episode.created_at}</span>
                        </div>
                    </div>
                    <button className="close-button" onClick={onClose}>✕</button>
                </div>

                <div className="modal-body">
                    <section className="summary-section">
                        <h3>Summary</h3>
                        <p className="summary-text">{episode.summary}</p>
                    </section>

                    {episode.key_topics.length > 0 && (
                        <section className="topics-section">
                            <h3>Key Topics</h3>
                            <div className="topic-tags">
                                {episode.key_topics.map((topic, i) => (
                                    <span key={i} className="topic-tag">{topic}</span>
                                ))}
                            </div>
                        </section>
                    )}

                    <section className="speakers-section">
                        <h3>Speakers</h3>
                        <div className="speakers-list">
                            {episode.speakers.map((speaker, i) => (
                                <span key={i} className="speaker-badge">👤 {speaker}</span>
                            ))}
                        </div>
                    </section>

                    <section className="actions-section">
                        <h3>Actions</h3>
                        <div className="action-buttons">
                            <button className="btn-primary" onClick={downloadTranscript}>
                                ⬇️ Download Transcript
                            </button>
                            <button className="btn-primary" onClick={downloadSummary}>
                                ⬇️ Download Summary
                            </button>
                            <button className="btn-primary" onClick={onOpenChat}>
                                💬 Chat About Episode
                            </button>
                            <button
                                className="btn-secondary"
                                onClick={loadTranscript}
                                disabled={loadingTranscript}
                            >
                                {loadingTranscript ? '⏳ Loading...' : showTranscript ? '🔼 Hide Transcript' : '🔽 Show Transcript'}
                            </button>
                        </div>
                    </section>

                    {showTranscript && transcript && (
                        <section className="transcript-section">
                            <div className="transcript-header">
                                <h3>Full Transcript</h3>
                                <input
                                    type="text"
                                    placeholder="🔍 Search in transcript..."
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="search-input"
                                />
                            </div>
                            <div className="transcript-content">
                                {highlightText(transcript)}
                            </div>
                        </section>
                    )}
                </div>
            </div>
        </div>
    );
}

export default EpisodeDetailModal;
