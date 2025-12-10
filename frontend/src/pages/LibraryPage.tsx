import { useState, useEffect } from 'react';
import './LibraryPage.css';
import { summarizationApi, Summary } from '../api';
import EpisodeDetailModal from '../components/EpisodeDetailModal';
import ChatPopup from '../components/ChatPopup';

function LibraryPage() {
    const [summaries, setSummaries] = useState<Summary[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedEpisode, setSelectedEpisode] = useState<Summary | null>(null);
    const [chatEpisode, setChatEpisode] = useState<Summary | null>(null);
    const [selectedForDownload, setSelectedForDownload] = useState<Set<string>>(new Set());

    useEffect(() => {
        loadSummaries();
    }, []);

    const loadSummaries = async () => {
        try {
            setIsLoading(true);
            const data = await summarizationApi.getSummaries();
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
        // Keep modal open - don't close it when opening chat
    };

    const handleToggleSelect = (episodeTitle: string) => {
        setSelectedForDownload(prev => {
            const newSet = new Set(prev);
            if (newSet.has(episodeTitle)) {
                newSet.delete(episodeTitle);
            } else {
                newSet.add(episodeTitle);
            }
            return newSet;
        });
    };

    const handleDownloadSelected = () => {
        const selectedSummaries = summaries.filter(s => selectedForDownload.has(s.episode_title));

        if (selectedSummaries.length === 0) {
            alert('No episodes selected');
            return;
        }

        // Format summaries with complete structured markdown
        const content = selectedSummaries.map(summary => {
            let markdown = `# ${summary.episode_title}\n`;
            markdown += `**Podcast:** ${summary.podcast_name}  \n`;
            markdown += `**Duration:** ${summary.duration || 'N/A'}  \n`;
            markdown += `**Created:** ${summary.created_at}\n\n`;
            markdown += `${'='.repeat(80)}\n\n`;

            // Hook
            if (summary.hook) {
                markdown += `> ${summary.hook}\n\n`;
                markdown += `${'='.repeat(80)}\n\n`;
            }

            // Main Summary
            markdown += `## Summary\n\n${summary.summary}\n\n`;
            markdown += `${'='.repeat(80)}\n\n`;

            // Key Takeaways
            if (summary.key_takeaways && summary.key_takeaways.length > 0) {
                markdown += `## Key Takeaways\n\n`;
                summary.key_takeaways.forEach((takeaway, i) => {
                    markdown += `${i + 1}. **${takeaway.concept}**\n`;
                    markdown += `   ${takeaway.explanation}\n\n`;
                });
                markdown += `${'='.repeat(80)}\n\n`;
            }

            // Actionable Advice
            if (summary.actionable_advice && summary.actionable_advice.length > 0) {
                markdown += `## Actionable Advice\n\n`;
                summary.actionable_advice.forEach((advice, i) => {
                    markdown += `${i + 1}. ${advice}\n`;
                });
                markdown += `\n${'='.repeat(80)}\n\n`;
            }

            // Notable Quotes
            if (summary.quotes && summary.quotes.length > 0) {
                markdown += `## Notable Quotes\n\n`;
                summary.quotes.forEach((quote, i) => {
                    markdown += `${i + 1}. "${quote}"\n\n`;
                });
                markdown += `${'='.repeat(80)}\n\n`;
            }

            // Key Concepts
            if (summary.concepts && summary.concepts.length > 0) {
                markdown += `## Key Concepts\n\n`;
                summary.concepts.forEach((concept, i) => {
                    markdown += `${i + 1}. **${concept.term}**\n`;
                    markdown += `   ${concept.definition}\n\n`;
                });
                markdown += `${'='.repeat(80)}\n\n`;
            }

            // Different Perspectives
            if (summary.perspectives) {
                markdown += `## Different Perspectives\n\n${summary.perspectives}\n\n`;
                markdown += `${'='.repeat(80)}\n\n`;
            }

            // Key Topics
            if (summary.key_topics.length > 0) {
                markdown += `## Key Topics\n\n`;
                markdown += summary.key_topics.map(t => `- ${t}`).join('\n');
                markdown += `\n\n${'='.repeat(80)}\n\n`;
            }

            // Speakers
            markdown += `## Speakers\n\n${summary.speakers.join(', ')}\n\n`;
            markdown += `---\n\n`;

            return markdown;
        }).join('\n');

        // Download as markdown file
        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `podcast-summaries-${new Date().toISOString().split('T')[0]}.md`;
        a.click();
        URL.revokeObjectURL(url);

        // Clear selection after download
        setSelectedForDownload(new Set());
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
                <div>
                    <h1>📚 Podcast Library</h1>
                    <p className="subtitle">{summaries.length} episodes indexed</p>
                </div>
                {selectedForDownload.size > 0 && (
                    <button className="btn-primary" onClick={handleDownloadSelected}>
                        ⬇️ Download {selectedForDownload.size} {selectedForDownload.size === 1 ? 'Summary' : 'Summaries'}
                    </button>
                )}
            </div>

            <div className="summaries-grid">
                {summaries.map((summary, idx) => (
                    <div
                        key={idx}
                        className={`summary-card glass clickable ${selectedForDownload.has(summary.episode_title) ? 'selected' : ''}`}
                    >
                        <div className="card-select">
                            <input
                                type="checkbox"
                                checked={selectedForDownload.has(summary.episode_title)}
                                onChange={(e) => {
                                    e.stopPropagation();
                                    handleToggleSelect(summary.episode_title);
                                }}
                                className="episode-checkbox"
                                aria-label={`Select ${summary.episode_title}`}
                            />
                        </div>
                        <div onClick={() => handleEpisodeClick(summary)}>
                            <div className="card-header">
                                <div className="podcast-badge">{summary.podcast_name}</div>
                                <div className="duration">{summary.duration || 'N/A'}</div>
                            </div>

                            <h3 className="episode-title">{summary.episode_title}</h3>

                            {/* Show hook if available, otherwise show brief summary */}
                            {summary.hook && (
                                <div className="summary-text">💡 {summary.hook}</div>
                            )}
                            {!summary.hook && summary.summary && !summary.summary.includes('```json') && (
                                <div className="summary-text">{summary.summary.substring(0, 200)}...</div>
                            )}

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
                    isChatOpen={!!chatEpisode}
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
