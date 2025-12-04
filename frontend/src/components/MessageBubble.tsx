import './MessageBubble.css';
import { ChatMessage } from '../api';

interface MessageBubbleProps {
    message: ChatMessage;
}

function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.role === 'user';

    return (
        <div className={`message ${isUser ? 'user' : 'assistant'}`}>
            <div className="avatar">
                {isUser ? '👤' : '🤖'}
            </div>
            <div className="message-content">
                <div className={`bubble glass ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
                    <p>{message.content}</p>
                </div>

                {message.sources && message.sources.length > 0 && (
                    <div className="sources">
                        <div className="sources-header">📚 Sources:</div>
                        <div className="source-chips">
                            {message.sources.map((source, idx) => (
                                <div key={idx} className="source-chip glass">
                                    <div className="source-header">
                                        <span className="source-podcast">{source.podcast_name}</span>
                                        <span className="source-score">{(source.relevance_score * 100).toFixed(0)}%</span>
                                    </div>
                                    <div className="source-episode">{source.episode_title}</div>
                                    <div className="source-details">
                                        <span>{source.speaker}</span>
                                        <span>•</span>
                                        <span>{source.timestamp}</span>
                                    </div>
                                    <div className="source-snippet">"{source.text_snippet}"</div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default MessageBubble;
