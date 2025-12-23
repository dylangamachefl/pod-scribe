import { MessageSquare, Calendar, Clock, Heart } from 'lucide-react';
import { Summary } from '../api/types';
import './SmartCard.css';

interface SmartCardProps {
    summary: Summary;
    onChat: (summary: Summary) => void;
    onOpen: (summary: Summary) => void;
}

export function SmartCard({ summary, onChat, onOpen }: SmartCardProps) {
    // Fallback if hook is missing
    const displayHook = summary.hook || summary.summary.slice(0, 150) + '...';

    return (
        <div className="smart-card glass-panel" onClick={() => onOpen(summary)}>
            <div className="card-header">
                <div className="flex-1 overflow-hidden">
                    <div className="card-podcast">{summary.podcast_name}</div>
                    <div className="card-date">
                        <Calendar size={12} />
                        <span>{new Date(summary.created_at).toLocaleDateString()}</span>
                    </div>
                </div>
                {summary.is_favorite && (
                    <div className="favorite-indicator">
                        <Heart size={14} fill="#ef4444" color="#ef4444" />
                    </div>
                )}
            </div>

            <div className="card-body">
                <h3 className="card-title">{summary.episode_title}</h3>
                <div className="card-hook">
                    {displayHook}
                </div>
            </div>

            <div className="card-tags">
                {summary.key_topics.slice(0, 3).map(tag => (
                    <span key={tag} className="tag-pill">#{tag}</span>
                ))}
            </div>

            <div className="card-footer">
                <div className="footer-meta">
                    <Clock size={12} />
                    <span>{summary.duration || '20m'}</span>
                </div>
                <button
                    className="chat-action-btn"
                    onClick={(e) => {
                        e.stopPropagation();
                        onChat(summary);
                    }}
                    title="Chat about this episode"
                >
                    <MessageSquare size={16} />
                </button>
            </div>
        </div>
    );
}
