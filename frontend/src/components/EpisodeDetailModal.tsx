import { useState, useEffect } from 'react';
import './EpisodeDetailModal.css';
import { Summary } from '../api/types';
import { transcriptionApi } from '../api';
import AudioPlayer from './AudioPlayer';

interface EpisodeDetailModalProps {
    episode: Summary;
    onClose: () => void;
    onOpenChat: () => void;
    isChatOpen?: boolean;
}

function EpisodeDetailModal({ episode, onClose, onOpenChat, isChatOpen }: EpisodeDetailModalProps) {
    const [showTranscript, setShowTranscript] = useState(false);
    const [transcript, setTranscript] = useState<string | null>(null);
    const [loadingTranscript, setLoadingTranscript] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');

    // Handle Escape key to close modal
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                onClose();
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [onClose]);

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

    // Helper function to detect YouTube URLs
    const isYouTubeUrl = (url?: string): boolean => {
        if (!url) return false;
        return url.includes('youtube.com') || url.includes('youtu.be');
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
        <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="modal-title">
            <div
                className={`modal-content glass ${isChatOpen ? 'modal-shrunk' : ''}`}
                onClick={(e) => e.stopPropagation()}
            >
                <div className="modal-header">
                    <div>
                        <div className="podcast-badge">{episode.podcast_name}</div>
                        <h2 id="modal-title">{episode.episode_title}</h2>
                        <div className="episode-meta">
                            {episode.duration && <span>⏱️ {episode.duration}</span>}
                            <span>📅 {episode.created_at}</span>
                        </div>
                    </div>
                    <button className="close-button" onClick={onClose} aria-label="Close episode details">✕</button>
                </div>

                {/* Audio Player or YouTube Link */}
                {episode.audio_url && (
                    <div className="audio-section">
                        {isYouTubeUrl(episode.audio_url) ? (
                            <a
                                href={episode.audio_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="youtube-link glass"
                            >
                                <span className="youtube-icon">▶️</span>
                                <span>Watch on YouTube</span>
                                <span className="external-icon">↗</span>
                            </a>
                        ) : (
                            <AudioPlayer audioUrl={episode.audio_url} />
                        )}
                    </div>
                )}

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
                            <button className="btn-primary" onClick={downloadTranscript} aria-label="Download full transcript">
                                ⬇️ Download Transcript
                            </button>
                            <button className="btn-primary" onClick={downloadSummary} aria-label="Download episode summary">
                                ⬇️ Download Summary
                            </button>
                            <button className="btn-primary" onClick={onOpenChat} aria-label="Open chat to ask questions about this episode">
                                💬 Chat About Episode
                            </button>
                            <button
                                className="btn-secondary"
                                onClick={loadTranscript}
                                disabled={loadingTranscript}
                                aria-label={showTranscript ? 'Hide transcript' : 'Show full transcript'}
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
                                    aria-label="Search in transcript"
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
