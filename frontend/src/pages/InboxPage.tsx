import { useState, useEffect } from 'react';
import { transcriptionApi } from '../api';
import { Episode, TranscriptionStatus } from '../api/types';
import { ActionBar } from '../components/ActionBar';
import { FeedList } from '../components/FeedList';
import { LiveStatusBanner } from '../components/LiveStatusBanner';
import { ChevronDown } from 'lucide-react';
import './InboxPage.css';

export default function InboxPage() {
    const [episodes, setEpisodes] = useState<Episode[]>([]);
    const [selectedIds, setSelectedIds] = useState<string[]>([]);
    const [status, setStatus] = useState<TranscriptionStatus>({
        is_running: false,
        stage: 'idle',
        progress: 0,
        episodes_completed: 0,
        episodes_total: 0,
        gpu_usage: 0,
        vram_used_gb: 0,
        vram_total_gb: 0
    });
    const [isSyncing, setIsSyncing] = useState(false);
    const [notification, setNotification] = useState<{ message: string, type: 'success' | 'error' } | null>(null);

    // Filter & Sort State
    const [viewMode, setViewMode] = useState<'inbox' | 'all'>('inbox');
    const [feedFilter, setFeedFilter] = useState<string>('all');
    const [sortOrder, setSortOrder] = useState<'date_desc' | 'date_asc'>('date_desc');
    const [uniqueFeeds, setUniqueFeeds] = useState<string[]>([]);

    const loadData = async () => {
        try {
            // Always fetch all episodes
            const data = await transcriptionApi.getAllEpisodes();
            // Extract unique feeds
            const feeds = Array.from(new Set(data.map(e => e.feed_title).filter(Boolean))).sort();
            setUniqueFeeds(feeds);
            // Filter for "New Arrivals" (unseen episodes)
            let filteredData = data;
            if (viewMode === 'inbox') {
                filteredData = data.filter(ep => !ep.is_seen);
            }
            setEpisodes(filteredData);
            const currentStatus = await transcriptionApi.getTranscriptionStatus();
            setStatus(currentStatus);
        } catch (error) {
            console.error('Failed to load inbox data:', error);
        }
    };

    useEffect(() => {
        loadData();
        const interval = setInterval(loadData, 5000); // 5s poll
        return () => clearInterval(interval);
    }, [viewMode]); // Reload when view mode changes

    const handleSync = async () => {
        setIsSyncing(true);
        try {
            await transcriptionApi.fetchEpisodes();
            await loadData(); // Reload immediately
            showNotification('Feeds synced successfully', 'success');
        } catch (error) {
            console.error('Sync failed:', error);
            showNotification('Failed to sync feeds', 'error');
        } finally {
            setIsSyncing(false);
        }
    };

    const handleToggleSelect = (id: string, selected: boolean) => {
        if (selected) {
            setSelectedIds(prev => [...prev, id]);
        } else {
            setSelectedIds(prev => prev.filter(item => item !== id));
        }
    };

    // Derived state for filtered/sorted list
    const filteredEpisodes = episodes
        .filter(ep => feedFilter === 'all' || ep.feed_title === feedFilter)
        .sort((a, b) => {
            const dateA = new Date(a.published_date).getTime();
            const dateB = new Date(b.published_date).getTime();
            return sortOrder === 'date_desc' ? dateB - dateA : dateA - dateB;
        });

    const handleSelectAll = (selected: boolean) => {
        if (selected) {
            setSelectedIds(filteredEpisodes.map(ep => ep.id));
        } else {
            setSelectedIds([]);
        }
    };

    const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
        setNotification({ message, type });
        setTimeout(() => setNotification(null), 3000);
    };

    const handleTranscribe = async () => {
        try {
            const response = await transcriptionApi.startTranscription({ episode_ids: selectedIds });
            // Auto mark as seen when transcribing
            await transcriptionApi.bulkSeenEpisodes(selectedIds, true);
            setSelectedIds([]); // Clear selection after start
            await loadData(); // Reload status and data
            showNotification(response.message || 'Transcription started successfully', 'success');
        } catch (error) {
            console.error('Transcription start failed:', error);
            showNotification('Failed to start transcription', 'error');
        }
    };

    const handleMarkAsSeen = async () => {
        try {
            await transcriptionApi.bulkSeenEpisodes(selectedIds, true);
            setSelectedIds([]);
            await loadData();
            showNotification('Marked as seen', 'success');
        } catch (error) {
            console.error('Failed to mark episodes as seen:', error);
            showNotification('Failed to mark as seen', 'error');
        }
    };

    const handlePlay = (url: string) => {
        window.open(url, '_blank');
    };

    return (
        <div className="inbox-page">
            <ActionBar
                selectedCount={selectedIds.length}
                onSync={handleSync}
                onTranscribe={handleTranscribe}
                onMarkSeen={handleMarkAsSeen}
                isSyncing={isSyncing}
            />

            <LiveStatusBanner status={status} />

            {notification && (
                <div className={`notification-banner ${notification.type}`} style={{
                    padding: '8px 16px',
                    margin: '8px 24px',
                    borderRadius: '8px',
                    backgroundColor: notification.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                    border: `1px solid ${notification.type === 'success' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`,
                    color: notification.type === 'success' ? '#10b981' : '#ef4444',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '14px',
                    fontWeight: 500
                }}>
                    {notification.message}
                </div>
            )}

            {/* Filter & Sort Controls */}
            <div className="filter-bar">
                <div className="view-mode-toggle">
                    <button
                        className={`view-toggle-btn ${viewMode === 'inbox' ? 'active' : ''}`}
                        onClick={() => setViewMode('inbox')}
                    >
                        New Arrivals
                    </button>
                    <button
                        className={`view-toggle-btn ${viewMode === 'all' ? 'active' : ''}`}
                        onClick={() => setViewMode('all')}
                    >
                        All Episodes
                    </button>
                </div>

                <div className="filter-separator" />

                <div className="styled-select-wrapper">
                    <select
                        className="styled-select"
                        value={feedFilter}
                        onChange={(e) => setFeedFilter(e.target.value)}
                    >
                        <option value="all">All Podcasts</option>
                        {uniqueFeeds.map(feed => (
                            <option key={feed} value={feed}>{feed}</option>
                        ))}
                    </select>
                    <ChevronDown size={14} className="select-icon" />
                </div>

                <div className="styled-select-wrapper">
                    <select
                        className="styled-select"
                        value={sortOrder}
                        onChange={(e) => setSortOrder(e.target.value as any)}
                    >
                        <option value="date_desc">Newest First</option>
                        <option value="date_asc">Oldest First</option>
                    </select>
                    <ChevronDown size={14} className="select-icon" />
                </div>

                <div className="episode-counter">
                    {filteredEpisodes.length} episodes
                </div>
            </div>

            <FeedList
                episodes={filteredEpisodes}
                selectedIds={selectedIds}
                onToggleSelect={handleToggleSelect}
                onSelectAll={handleSelectAll}
                isAllSelected={filteredEpisodes.length > 0 && selectedIds.length === filteredEpisodes.length}
                onPlay={handlePlay}
            />
        </div>
    );
}
