import { useState, useEffect } from 'react';
import { transcriptionApi } from '../api';
import type { Feed, FeedCreate } from '../api/types';
import './FeedManagerPage.css';

function FeedManagerPage() {
    const [feeds, setFeeds] = useState<Feed[]>([]);
    const [newFeedUrl, setNewFeedUrl] = useState('');
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadFeeds = async () => {
        try {
            const data = await transcriptionApi.getFeeds();
            setFeeds(data);
            setError(null);
        } catch (err) {
            setError('Failed to load feeds');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadFeeds();
    }, []);

    const handleAddFeed = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newFeedUrl.trim()) return;

        setSubmitting(true);
        try {
            await transcriptionApi.addFeed({ url: newFeedUrl } as FeedCreate);
            setNewFeedUrl('');
            await loadFeeds();
        } catch (err: any) {
            alert(err.response?.data?.detail || 'Failed to add feed');
        } finally {
            setSubmitting(false);
        }
    };

    const handleToggleFeed = async (feed: Feed) => {
        try {
            await transcriptionApi.updateFeed(feed.id, { active: !feed.active });
            await loadFeeds();
        } catch (err) {
            alert('Failed to update feed');
        }
    };

    const handleDeleteFeed = async (feed: Feed) => {
        if (!confirm(`Delete "${feed.title}"?`)) return;

        try {
            await transcriptionApi.deleteFeed(feed.id);
            await loadFeeds();
        } catch (err) {
            alert('Failed to delete feed');
        }
    };

    if (loading) {
        return <div className="feed-manager-page loading">Loading feeds...</div>;
    }

    return (
        <div className="feed-manager-page">
            <div className="page-header">
                <h1>📡 Feed Manager</h1>
                <p>Manage your podcast RSS feed subscriptions</p>
            </div>

            {/* Add New Feed */}
            <div className="add-feed-section">
                <h2>➕ Add New Feed</h2>
                <form onSubmit={handleAddFeed} className="add-feed-form">
                    <input
                        type="url"
                        placeholder="https://feeds.example.com/podcast.xml"
                        value={newFeedUrl}
                        onChange={(e) => setNewFeedUrl(e.target.value)}
                        required
                        className="feed-input"
                    />
                    <button type="submit" className="btn-primary" disabled={submitting}>
                        {submitting ? 'Adding...' : 'Add Feed'}
                    </button>
                </form>
            </div>

            {/* Feed List */}
            <div className="feeds-section">
                <h2>📋 Your Subscriptions</h2>

                {error && <div className="error">{error}</div>}

                {feeds.length === 0 ? (
                    <div className="empty-state">
                        No feeds yet. Add your first podcast feed above!
                    </div>
                ) : (
                    <div className="feeds-list">
                        {feeds.map((feed) => (
                            <div key={feed.id} className="feed-item">
                                <div className="feed-info">
                                    <div className="feed-status">
                                        {feed.active ? '✅' : '⏸️'}
                                    </div>
                                    <div className="feed-details">
                                        <div className="feed-title">{feed.title}</div>
                                        <div className="feed-url">{feed.url}</div>
                                    </div>
                                </div>
                                <div className="feed-actions">
                                    <button
                                        className="btn-secondary"
                                        onClick={() => handleToggleFeed(feed)}
                                    >
                                        {feed.active ? 'Deactivate' : 'Activate'}
                                    </button>
                                    <button
                                        className="btn-danger"
                                        onClick={() => handleDeleteFeed(feed)}
                                    >
                                        Delete
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

export default FeedManagerPage;
