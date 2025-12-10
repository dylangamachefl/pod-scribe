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

    // Extract the actual transcript filename from source_file path
    const getTranscriptFilename = (): string => {
        if (episode.source_file) {
            // Extract filename from path (e.g., ".../Huberman Lab/Episode Name.txt" -> "Episode Name")
            const pathParts = episode.source_file.replace(/\\/g, '/').split('/');
            const filename = pathParts[pathParts.length - 1]; // Get last part
            return filename.replace('.txt', ''); // Remove .txt extension
        }
        // Fallback to episode title if source_file not available
        return episode.episode_title;
    };

    // Format date to human-readable format
    const formatDate = (dateString: string): string => {
        try {
            const date = new Date(dateString);
            if (isNaN(date.getTime())) return dateString; // Return original if invalid

            return date.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
        } catch {
            return dateString;
        }
    };

    // Format duration to readable format
    const formatDuration = (duration?: string): string => {
        if (!duration) return 'N/A';

        // If already in readable format (e.g., "1h 23m"), return as is
        if (duration.includes('h') || duration.includes('m') || duration.includes('s')) {
            return duration;
        }

        // Try to parse as seconds
        const seconds = parseInt(duration);
        if (isNaN(seconds)) return duration;

        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        if (hours > 0) {
            return `${hours}h ${minutes}m`;
        }
        return `${minutes}m`;
    };

    const loadTranscript = async () => {
        if (transcript) {
            setShowTranscript(!showTranscript);
            return;
        }

        try {
            setLoadingTranscript(true);
            const episodeFilename = getTranscriptFilename();
            const data = await transcriptionApi.getTranscript(
                episode.podcast_name,
                episodeFilename
            );
            setTranscript(data.content);
            setShowTranscript(true);
        } catch (err) {
            console.error('Failed to load transcript:', err);
            alert(`Failed to load transcript. Episode filename: ${getTranscriptFilename()}`);
        } finally {
            setLoadingTranscript(false);
        }
    };

    const downloadTranscript = () => {
        const episodeFilename = getTranscriptFilename();
        const url = transcriptionApi.getTranscriptUrl(
            episode.podcast_name,
            episodeFilename
        );

        // Trigger download via temporary anchor tag
        const a = document.createElement('a');
        a.href = url;
        a.download = `${episode.episode_title}.txt`;
        a.target = '_blank'; // Open in new tab if download is blocked by browser policy
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    const downloadSummary = () => {
        // Build comprehensive summary text with all structured fields
        let summaryContent = `${episode.episode_title}\n`;
        summaryContent += `${episode.podcast_name}\n`;
        summaryContent += `\n${'='.repeat(80)}\n\n`;

        // Hook
        if (episode.hook) {
            summaryContent += `${episode.hook}\n\n`;
            summaryContent += `${'='.repeat(80)}\n\n`;
        }

        // Main Summary
        summaryContent += `SUMMARY\n\n${episode.summary}\n\n`;
        summaryContent += `${'='.repeat(80)}\n\n`;

        // Key Takeaways
        if (episode.key_takeaways && episode.key_takeaways.length > 0) {
            summaryContent += `KEY TAKEAWAYS\n\n`;
            episode.key_takeaways.forEach((takeaway, i) => {
                summaryContent += `${i + 1}. ${takeaway.concept}\n`;
                summaryContent += `   ${takeaway.explanation}\n\n`;
            });
            summaryContent += `${'='.repeat(80)}\n\n`;
        }

        // Actionable Advice
        if (episode.actionable_advice && episode.actionable_advice.length > 0) {
            summaryContent += `ACTIONABLE ADVICE\n\n`;
            episode.actionable_advice.forEach((advice, i) => {
                summaryContent += `${i + 1}. ${advice}\n`;
            });
            summaryContent += `\n${'='.repeat(80)}\n\n`;
        }

        // Notable Quotes
        if (episode.quotes && episode.quotes.length > 0) {
            summaryContent += `NOTABLE QUOTES\n\n`;
            episode.quotes.forEach((quote, i) => {
                summaryContent += `${i + 1}. "${quote}"\n\n`;
            });
            summaryContent += `${'='.repeat(80)}\n\n`;
        }

        // Key Concepts
        if (episode.concepts && episode.concepts.length > 0) {
            summaryContent += `KEY CONCEPTS\n\n`;
            episode.concepts.forEach((concept, i) => {
                summaryContent += `${i + 1}. ${concept.term}\n`;
                summaryContent += `   ${concept.definition}\n\n`;
            });
            summaryContent += `${'='.repeat(80)}\n\n`;
        }

        // Different Perspectives
        if (episode.perspectives) {
            summaryContent += `DIFFERENT PERSPECTIVES\n\n${episode.perspectives}\n\n`;
            summaryContent += `${'='.repeat(80)}\n\n`;
        }

        // Key Topics
        if (episode.key_topics.length > 0) {
            summaryContent += `KEY TOPICS\n\n`;
            summaryContent += episode.key_topics.map(t => `• ${t}`).join('\n');
            summaryContent += `\n\n${'='.repeat(80)}\n\n`;
        }

        // Speakers
        summaryContent += `SPEAKERS\n\n${episode.speakers.join(', ')}`;

        // Create and download
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
                            {episode.duration && <span>⏱️ {formatDuration(episode.duration)}</span>}
                            <span>📅 {formatDate(episode.created_at)}</span>
                            {episode.total_processing_time_ms && (
                                <span className="processing-time" title={`Stage 1: ${(episode.stage1_processing_time_ms || 0) / 1000}s | Stage 2: ${(episode.stage2_processing_time_ms || 0) / 1000}s`}>
                                    ⚡ {(episode.total_processing_time_ms / 1000).toFixed(1)}s
                                </span>
                            )}
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
                    {/* Hook - One-sentence summary */}
                    {episode.hook && (
                        <section className="hook-section">
                            <div className="hook-text">"{episode.hook}"</div>
                        </section>
                    )}

                    {/* Main Summary */}
                    <section className="summary-section">
                        <h3>Summary</h3>
                        <p className="summary-text">{episode.summary}</p>
                    </section>

                    {/* Key Takeaways */}
                    {episode.key_takeaways && episode.key_takeaways.length > 0 && (
                        <section className="takeaways-section">
                            <h3>Key Takeaways</h3>
                            <div className="takeaways-list">
                                {episode.key_takeaways.map((takeaway, i) => (
                                    <div key={i} className="takeaway-item">
                                        <strong>{takeaway.concept}</strong>
                                        <p>{takeaway.explanation}</p>
                                    </div>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* Actionable Advice */}
                    {episode.actionable_advice && episode.actionable_advice.length > 0 && (
                        <section className="advice-section">
                            <h3>Actionable Advice</h3>
                            <ul className="advice-list">
                                {episode.actionable_advice.map((advice, i) => (
                                    <li key={i}>{advice}</li>
                                ))}
                            </ul>
                        </section>
                    )}

                    {/* Notable Quotes */}
                    {episode.quotes && episode.quotes.length > 0 && (
                        <section className="quotes-section">
                            <h3>Notable Quotes</h3>
                            <div className="quotes-list">
                                {episode.quotes.map((quote, i) => (
                                    <blockquote key={i} className="quote-item">
                                        "{quote}"
                                    </blockquote>
                                ))}
                            </div>
                        </section>
                    )}

                    {/* Key Concepts */}
                    {episode.concepts && episode.concepts.length > 0 && (
                        <section className="concepts-section">
                            <h3>Key Concepts</h3>
                            <dl className="concepts-list">
                                {episode.concepts.map((concept, i) => (
                                    <div key={i} className="concept-item">
                                        <dt><strong>{concept.term}</strong></dt>
                                        <dd>{concept.definition}</dd>
                                    </div>
                                ))}
                            </dl>
                        </section>
                    )}

                    {/* Perspectives */}
                    {episode.perspectives && (
                        <section className="perspectives-section">
                            <h3>Different Perspectives</h3>
                            <p className="perspectives-text">{episode.perspectives}</p>
                        </section>
                    )}

                    {/* Key Topics (fallback or supplementary) */}
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
