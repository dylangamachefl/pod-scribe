import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import {
    Inbox,
    Library,
    Activity,
    Radio,
    Layout,
    BarChart3
} from 'lucide-react';
import { transcriptionApi, summarizationApi } from '../api';
import './Sidebar.css';

export function Sidebar() {
    const [queueCount, setQueueCount] = useState(0);
    const [isProcessing, setIsProcessing] = useState(false);
    const [topTags, setTopTags] = useState<string[]>([]);

    useEffect(() => {
        const loadData = async () => {
            try {
                // Get queue count
                const queue = await transcriptionApi.getEpisodeQueue();
                setQueueCount(queue.length);

                // Get processing status
                const status = await transcriptionApi.getTranscriptionStatus();
                setIsProcessing(status.is_running);

                // Get top tags (simplified logic: just get all summaries and aggregate for now)
                // In a real app with backend support, we'd hit a tags endpoint
                const summaries = await summarizationApi.getSummaries();
                const tagCounts: Record<string, number> = {};
                summaries.forEach(s => {
                    s.key_topics.forEach(t => {
                        tagCounts[t] = (tagCounts[t] || 0) + 1;
                    });
                });
                const sortedTags = Object.entries(tagCounts)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 5)
                    .map(([tag]) => tag);
                setTopTags(sortedTags);

            } catch (error) {
                console.error('Sidebar data fetch error:', error);
            }
        };

        loadData();
        // Poll every 10s
        const interval = setInterval(loadData, 10000);
        return () => clearInterval(interval);
    }, []);

    return (
        <aside className="app-sidebar glass">
            <div className="sidebar-header">
                <div className="logo-container">
                    <span className="logo-icon">🎙️</span>
                    <span className="logo-text">Knowledge OS</span>
                </div>
            </div>

            <nav className="sidebar-nav">
                <div className="nav-section">
                    <div className="section-label">Inbox</div>
                    <NavLink
                        to="/inbox"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <Inbox size={18} />
                        <span className="nav-text">New Arrivals</span>
                        {queueCount > 0 && <span className="badge count">{queueCount}</span>}
                    </NavLink>
                    {isProcessing && (
                        <div className="nav-item processing">
                            <Activity size={18} className="spin" />
                            <span className="nav-text">Processing...</span>
                            <span className="status-dot pulse"></span>
                        </div>
                    )}
                </div>

                <div className="nav-section">
                    <div className="section-label">Library</div>
                    <NavLink
                        to="/library"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <Library size={18} />
                        <span className="nav-text">All Summaries</span>
                    </NavLink>
                    <NavLink
                        to="/favorites"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <Layout size={18} />
                        <span className="nav-text">Favorites</span>
                    </NavLink>
                </div>

                <div className="nav-section">
                    <div className="section-label">Smart Tags</div>
                    <div className="tags-list">
                        {topTags.map(tag => (
                            <NavLink
                                key={tag}
                                to={`/library?tag=${encodeURIComponent(tag)}`}
                                className="nav-item tag-item"
                            >
                                <span className="hash">#</span>
                                <span className="nav-text">{tag}</span>
                            </NavLink>
                        ))}
                        {topTags.length === 0 && (
                            <div className="empty-tags">Indexing tags...</div>
                        )}
                    </div>
                </div>

                <div className="nav-section mt-auto">
                    <div className="section-label">System</div>
                    <NavLink
                        to="/feeds"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <Radio size={18} />
                        <span className="nav-text">Manage Feeds</span>
                    </NavLink>
                    <NavLink
                        to="/system"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <BarChart3 size={18} />
                        <span className="nav-text">System Health</span>
                    </NavLink>
                </div>
            </nav>
        </aside>
    );
}
