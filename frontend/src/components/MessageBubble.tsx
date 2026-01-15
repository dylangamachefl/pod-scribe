import { Play } from 'lucide-react';
import './MessageBubble.css';
import { ChatMessage } from '../api';
import { useAudio } from '../context/AudioContext';

interface MessageBubbleProps {
    message: ChatMessage;
}

function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.role === 'user';
    const { playAt } = useAudio();

    // Simple function to highlight footnotes in text
    // Assuming the LLM uses [1], [2] etc. format
    const renderContent = (content: string) => {
        if (isUser) return <p>{content}</p>;

        const parts = content.split(/(\[\d+\])/g);
        return (
            <p>
                {parts.map((part, i) => {
                    const match = part.match(/\[(\d+)\]/);
                    if (match) {
                        const index = parseInt(match[1]) - 1;
                        return (
                            <span
                                key={i}
                                className="footnote-tag"
                                onClick={() => {
                                    if (message.sources && message.sources[index]) {
                                        const source = message.sources[index];
                                        playAt(source.audio_url, source.timestamp);
                                    }
                                }}
                            >
                                {part}
                            </span>
                        );
                    }
                    return part;
                })}
            </p>
        );
    };

    return (
        <div className={`message ${isUser ? 'user' : 'assistant'}`}>
            <div className="avatar">
                {isUser ? '👤' : '🤖'}
            </div>
            <div className="message-content">
                <div className={`bubble glass ${isUser ? 'user-bubble' : 'assistant-bubble'}`}>
                    {renderContent(message.content)}
                </div>

                {message.sources && message.sources.length > 0 && (
                    <div className="sources">
                        <div className="sources-header">📚 Sources:</div>
                        <div className="source-chips">
                            {message.sources.map((source, idx) => (
                                <button
                                    key={idx}
                                    className="source-chip glass interactive-chip"
                                    onClick={() => playAt(source.audio_url, source.timestamp)}
                                >
                                    <div className="source-index">[{idx + 1}]</div>
                                    <div className="source-info">
                                        <div className="source-header">
                                            <span className="source-podcast">{source.podcast_name}</span>
                                            <Play size={12} className="play-icon" />
                                        </div>
                                        <div className="source-episode">{source.episode_title}</div>
                                        <div className="source-details">
                                            <span>{source.speaker}</span>
                                            <span>•</span>
                                            <span>{source.timestamp}</span>
                                        </div>
                                    </div>
                                    {/* <div className="source-snippet">"{source.text_snippet}"</div> */}
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default MessageBubble;
