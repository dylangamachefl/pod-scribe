import { useState, useEffect } from 'react';
import { transcriptionApi } from '../api';
import type { Episode } from '../api/types';
import './EpisodeQueuePage.css';

function EpisodeQueuePage() {
    const [episodes, setEpisodes] = useState<Episode[]>([]);
    const [loading, setLoading] = useState(true);
    const [fetching, setFetching] = useState(false);
    const [filterPodcast, setFilterPodcast] = useState('All Podcasts');
    const [filterTime, setFilterTime] = useState<number>(7); // 7 days, 30 days, or 0 for all time

    const loadEpisodes = async () => {
        try {
            const data = await transcriptionApi.getEpisodeQueue();
            setEpisodes(data);
        } catch (err) {
            console.error('Failed to load episodes:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadEpisodes();
    }, []);

    const handleFetchEpisodes = async () => {
        setFetching(true);
        try {
            const result = await transcriptionApi.fetchEpisodes(filterTime || undefined);
            alert(`Added ${result.new_episodes} new episode(s) to queue`);
            await loadEpisodes();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to fetch episodes');
        } finally {
            setFetching(false);
        }
    };

    const handleToggleSelect = async (episode: Episode) => {
        // Optimistic UI update - update immediately for better UX
        setEpisodes((prev) =>
            prev.map((ep) =>
                ep.id === episode.id ? { ...ep, selected: !ep.selected } : ep
            )
        );

        try {
            console.log('Toggling selection for episode:', episode.id, 'to', !episode.selected);
            await transcriptionApi.selectEpisode(episode.id, !episode.selected);
            console.log('Selection API call succeeded, reloading episodes...');
            // Reload to ensure consistency with backend
            await loadEpisodes();
        } catch (err: any) {
            console.error('Failed to toggle selection:', err);
            console.error('Error details:', {
                message: err.message,
                response: err.response?.data,
                status: err.response?.status
            });
            alert(`Failed to update selection: ${err.response?.data?.detail || err.message}`);
            // Revert optimistic update on error
            await loadEpisodes();
        }
    };

    const handleSelectAll = async () => {
        const ids = filteredEpisodes.map((ep) => ep.id);
        try {
            await transcriptionApi.bulkSelectEpisodes(ids, true);
            await loadEpisodes();
        } catch (err) {
            console.error('Failed to select all:', err);
        }
    };

    const handleDeselectAll = async () => {
        const ids = filteredEpisodes.map((ep) => ep.id);
        try {
            await transcriptionApi.bulkSelectEpisodes(ids, false);
            await loadEpisodes();
        } catch (err) {
            console.error('Failed to deselect all:', err);
        }
    };

    const podcasts = ['All Podcasts', ...new Set(episodes.map((ep) => ep.feed_title))];

    // Apply time-based filtering
    const getFilteredByTime = (eps: Episode[]) => {
        if (filterTime === 0) return eps; // All time

        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - filterTime);

        return eps.filter((ep) => {
            if (!ep.published_date) return true; // Include episodes without dates
            const publishedDate = new Date(ep.published_date);
            return publishedDate >= cutoffDate;
        });
    };

    // Apply both podcast and time filters
    const timeFilteredEpisodes = getFilteredByTime(episodes);
    const filteredEpisodes =
        filterPodcast === 'All Podcasts'
            ? timeFilteredEpisodes
            : timeFilteredEpisodes.filter((ep) => ep.feed_title === filterPodcast);
    const selectedCount = episodes.filter((ep) => ep.selected).length;

    if (loading) {
        return <div className="episode-queue-page loading">Loading episodes...</div>;
    }

    return (
        <div className="episode-queue-page">
            <div className="page-header">
                <h1>📥 Episode Queue</h1>
                <p>Fetch and select episodes to transcribe</p>
            </div>

            {/* Fetch Episodes */}
            <div className="fetch-section">
                <h2>🔄 Fetch New Episodes</h2>
                <p>Fetch new episodes from your active feeds without transcribing them</p>
                <button onClick={handleFetchEpisodes} disabled={fetching} className="btn-primary">
                    {fetching ? 'Fetching...' : '🔄 Fetch Episodes'}
                </button>
            </div>

            {/* Episode Queue */}
            <div className="queue-section">
                <h2>📋 Pending Episodes</h2>

                {episodes.length === 0 ? (
                    <div className="empty-state">
                        No episodes in the queue. Click 'Fetch Episodes' to add some!
                    </div>
                ) : (
                    <>
                        <div className="queue-controls">
                            <div className="stats">
                                <span className="stat">Total: {episodes.length}</span>
                                <span className="stat selected">Selected: {selectedCount}</span>
                            </div>
                            <div className="actions">
                                <select
                                    value={filterTime}
                                    onChange={(e) => setFilterTime(Number(e.target.value))}
                                    className="filter-select"
                                    aria-label="Filter episodes by time"
                                >
                                    <option value={7}>Last 7 Days</option>
                                    <option value={30}>Last 30 Days</option>
                                    <option value={0}>All Time</option>
                                </select>
                                <select
                                    value={filterPodcast}
                                    onChange={(e) => setFilterPodcast(e.target.value)}
                                    className="filter-select"
                                    aria-label="Filter episodes by podcast"
                                >
                                    {podcasts.map((p) => (
                                        <option key={p} value={p}>
                                            {p}
                                        </option>
                                    ))}
                                </select>
                                <button onClick={handleSelectAll} className="btn-secondary">
                                    ✅ Select All
                                </button>
                                <button onClick={handleDeselectAll} className="btn-secondary">
                                    ❌ Deselect All
                                </button>
                            </div>
                        </div>

                        <div className="episodes-list">
                            {filteredEpisodes.map((episode) => (
                                <div key={episode.id} className="episode-item">
                                    <input
                                        type="checkbox"
                                        checked={episode.selected}
                                        onChange={() => handleToggleSelect(episode)}
                                        className="episode-checkbox"
                                    />
                                    <div className="episode-info">
                                        <div className="episode-title">{episode.episode_title}</div>
                                        <div className="episode-meta">
                                            <span className="podcast-name">
                                                📻 {episode.feed_title}
                                            </span>
                                            <span className="publish-date">
                                                📅{' '}
                                                {new Date(episode.published_date).toLocaleDateString()}
                                            </span>
                                            {episode.duration && (
                                                <span className="duration">⏱️ {episode.duration}</span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

export default EpisodeQueuePage;
