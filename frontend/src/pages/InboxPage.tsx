import { useState, useEffect } from 'react';
import { transcriptionApi } from '../api';
import { Episode, TranscriptionStatus } from '../api/types';
import { ActionBar } from '../components/ActionBar';
import { FeedList } from '../components/FeedList';
import { LiveStatusBanner } from '../components/LiveStatusBanner';

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
            // Filter for "New Arrivals" (fetched in last 24 hours)
            const twentyFourHoursAgo = new Date();
            twentyFourHoursAgo.setHours(twentyFourHoursAgo.getHours() - 24);
            let filteredData = data;
            if (viewMode === 'inbox') {
                filteredData = data.filter(ep => {
                    if (!ep.fetched_date) return false;
                    return new Date(ep.fetched_date) >= twentyFourHoursAgo;
                });
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
        } catch (error) {
            console.error('Sync failed:', error);
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

    const handleTranscribe = async () => {
        try {
            await transcriptionApi.startTranscription({ episode_ids: selectedIds });
            setSelectedIds([]); // Clear selection after start
            await loadData(); // Reload status
        } catch (error) {
            console.error('Transcription start failed:', error);
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
                isSyncing={isSyncing}
            />

            <LiveStatusBanner status={status} />

            {/* Filter & Sort Controls */}
            <div className="flex items-center gap-4 px-8 py-4 border-b border-slate-700/50 bg-slate-900/40 backdrop-blur-sm sticky top-0 z-10 text-sm">
                <div className="flex items-center gap-2 bg-slate-800/50 rounded-lg p-1 border border-slate-700/50">
                    <button
                        className={`px-3 py-1.5 rounded-md transition-colors ${viewMode === 'inbox' ? 'bg-indigo-500/20 text-indigo-300 font-medium' : 'text-slate-400 hover:text-slate-200'}`}
                        onClick={() => setViewMode('inbox')}
                    >
                        New Arrivals
                    </button>
                    <button
                        className={`px-3 py-1.5 rounded-md transition-colors ${viewMode === 'all' ? 'bg-indigo-500/20 text-indigo-300 font-medium' : 'text-slate-400 hover:text-slate-200'}`}
                        onClick={() => setViewMode('all')}
                    >
                        All Episodes
                    </button>
                </div>

                <div className="h-4 w-px bg-slate-700 mx-2" />

                <select
                    className="bg-slate-800/50 text-slate-300 border border-slate-700/50 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    value={feedFilter}
                    onChange={(e) => setFeedFilter(e.target.value)}
                >
                    <option value="all">All Podcasts</option>
                    {uniqueFeeds.map(feed => (
                        <option key={feed} value={feed}>{feed}</option>
                    ))}
                </select>

                <select
                    className="bg-slate-800/50 text-slate-300 border border-slate-700/50 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    value={sortOrder}
                    onChange={(e) => setSortOrder(e.target.value as any)}
                >
                    <option value="date_desc">Newest First</option>
                    <option value="date_asc">Oldest First</option>
                </select>

                <div className="ml-auto text-slate-400">
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
