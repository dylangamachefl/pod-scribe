import { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
    Inbox,
    Library,
    Radio,
    Layout,
    BarChart3
} from 'lucide-react';
import { transcriptionApi } from '../api';
import './Sidebar.css';

export function Sidebar() {
    const location = useLocation();
    const [queueCount, setQueueCount] = useState(0);
    const [feeds, setFeeds] = useState<{ id: string, title: string }[]>([]);

    useEffect(() => {
        const loadData = async () => {
            try {
                // Get queue count (unseen episodes)
                const allEpisodes = await transcriptionApi.getAllEpisodes();
                const unseenCount = allEpisodes.filter(ep => !ep.is_seen).length;
                setQueueCount(unseenCount);

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
                    <div className="section-label">Main</div>
                    <NavLink
                        to="/dashboard"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <BarChart3 size={18} />
                        <span className="nav-text">Overview</span>
                    </NavLink>
                    <NavLink
                        to="/inbox"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <Inbox size={18} />
                        <span className="nav-text">New Arrivals</span>
                        {queueCount > 0 && <span className="badge count">{queueCount}</span>}
                    </NavLink>
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
                    <div className="section-label">Settings</div>
                    <NavLink
                        to="/feeds"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <Radio size={18} />
                        <span className="nav-text">Manage Feeds</span>
                    </NavLink>
                </div>
            </nav>
        </aside>
    );
}
