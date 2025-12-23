import { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
    Inbox,
    Library,
    Activity,
    Radio,
    Layout,
    BarChart3
} from 'lucide-react';
import { transcriptionApi } from '../api';
import './Sidebar.css';

export function Sidebar() {
    const location = useLocation();
    const [queueCount, setQueueCount] = useState(0);
    const [isProcessing, setIsProcessing] = useState(false);
    const [feeds, setFeeds] = useState<{ id: string, title: string }[]>([]);

    useEffect(() => {
        const loadData = async () => {
            try {
                // Get queue count (unseen episodes)
                const allEpisodes = await transcriptionApi.getAllEpisodes();
                const unseenCount = allEpisodes.filter(ep => !ep.is_seen).length;
                setQueueCount(unseenCount);

                // Get processing status
                const status = await transcriptionApi.getTranscriptionStatus();
                setIsProcessing(status.is_running);

                // Get feeds instead of tags
                const feedsList = await transcriptionApi.getFeeds();
                setFeeds(feedsList.map(f => ({ id: f.id, title: f.title })));

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
                        className={() => {
                            const isLibrary = location.pathname === '/library';
                            const hasParams = new URLSearchParams(location.search).has('feed') || new URLSearchParams(location.search).has('tag');
                            return `nav-item ${isLibrary && !hasParams ? 'active' : ''}`;
                        }}
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
                    <div className="section-label">Feeds</div>
                    <div className="tags-list">
                        {feeds.map(feed => (
                            <NavLink
                                key={feed.id}
                                to={`/library?feed=${encodeURIComponent(feed.title)}`}
                                className={() => {
                                    const params = new URLSearchParams(location.search);
                                    const isActive = location.pathname === '/library' && params.get('feed') === feed.title;
                                    return `nav-item tag-item ${isActive ? 'active' : ''}`;
                                }}
                            >
                                <Radio size={14} className="feed-nav-icon" />
                                <span className="nav-text">{feed.title}</span>
                            </NavLink>
                        ))}
                        {feeds.length === 0 && (
                            <div className="empty-tags">No feeds active</div>
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
