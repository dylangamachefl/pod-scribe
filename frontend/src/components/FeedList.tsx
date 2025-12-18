import { Play, Check, Clock, Radio } from 'lucide-react';
import { Episode } from '../api/types';
import './FeedList.css';

interface FeedListProps {
    episodes: Episode[];
    selectedIds: string[];
    onToggleSelect: (id: string, selected: boolean) => void;
    onSelectAll?: (selected: boolean) => void;
    isAllSelected?: boolean;
    onPlay: (url: string) => void;
}

export function FeedList({ episodes, selectedIds, onToggleSelect, onPlay, onSelectAll, isAllSelected }: FeedListProps) {
    if (episodes.length === 0) {
        return (
            <div className="empty-feed-state">
                <div className="empty-icon-wrapper">
                    <Radio size={48} />
                </div>
                <h3>Your inbox is empty</h3>
                <p>Sync your feeds to check for new episodes.</p>
            </div>
        );
    }

    return (
        <div className="feed-list">
            <div className="feed-header">
                <div className="col-select">
                    {onSelectAll && (
                        <div
                            className={`checkbox ${isAllSelected ? 'checked' : ''}`}
                            onClick={() => onSelectAll(!isAllSelected)}
                            title="Select All"
                        >
                            {isAllSelected && <Check size={14} />}
                        </div>
                    )}
                </div>
                <div className="col-title">Episode</div>
                <div className="col-feed">Podcast</div>
                <div className="col-date">Date</div>
                <div className="col-status">Status</div>
                <div className="col-action">Action</div>
            </div>

            <div className="feed-rows">
                {episodes.map(episode => {
                    const isSelected = selectedIds.includes(episode.id);
                    return (
                        <div
                            key={episode.id}
                            className={`feed-row ${isSelected ? 'selected' : ''}`}
                            onClick={() => onToggleSelect(episode.id, !isSelected)}
                        >
                            <div className="col-select">
                                <div className={`checkbox ${isSelected ? 'checked' : ''}`}>
                                    {isSelected && <Check size={14} />}
                                </div>
                            </div>
                            <div className="col-title">
                                <div className="episode-title">{episode.episode_title}</div>
                                <div className="mobile-meta">{episode.feed_title}</div>
                            </div>
                            <div className="col-feed">
                                <span className="feed-pill">{episode.feed_title}</span>
                            </div>
                            <div className="col-date">
                                <Clock size={14} className="date-icon" />
                                {new Date(episode.published_date).toLocaleDateString()}
                            </div>
                            <div className="col-status">
                                {(() => {
                                    // Calculate if episode is "New" (fetched in last 24 hours)
                                    const twentyFourHoursAgo = new Date();
                                    twentyFourHoursAgo.setHours(twentyFourHoursAgo.getHours() - 24);
                                    const fetchedDate = new Date(episode.fetched_date || 0);
                                    const isNew = fetchedDate >= twentyFourHoursAgo;

                                    if (isNew) {
                                        return <span className="status-badge status-new">New</span>;
                                    } else if (episode.status === 'PENDING') {
                                        return <span className="status-badge status-pending">Pending</span>;
                                    } else if (episode.status === 'COMPLETED') {
                                        return <span className="status-badge status-processed">Processed</span>;
                                    } else {
                                        return <span className="status-badge status-pending">{episode.status}</span>;
                                    }
                                })()}
                            </div>
                            <div className="col-action">
                                <button
                                    className="row-play-btn"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onPlay(episode.audio_url);
                                    }}
                                >
                                    <Play size={16} fill="currentColor" />
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
