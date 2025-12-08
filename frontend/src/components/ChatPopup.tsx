import { useState, useRef, useEffect } from 'react';
import './ChatPopup.css';
import { api, ChatMessage, Summary } from '../api';
import MessageBubble from './MessageBubble';

interface ChatPopupProps {
    episode: Summary;
    onClose: () => void;
}

function ChatPopup({ episode, onClose }: ChatPopupProps) {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Handle Escape key to close chat
    useEffect(() => {
        const handleEscape = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                onClose();
            }
        };

        document.addEventListener('keydown', handleEscape);
        return () => document.removeEventListener('keydown', handleEscape);
    }, [onClose]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage: ChatMessage = {
            role: 'user',
            content: input,
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            // Build conversation history
            const history = messages.map(msg => ({
                role: msg.role,
                content: msg.content,
            }));

            // Call episode-specific chat endpoint
            const response = await api.chatWithEpisode(episode.episode_title, input, history);

            const assistantMessage: ChatMessage = {
                role: 'assistant',
                content: response.answer,
                sources: response.sources,
                timestamp: new Date(),
            };

            setMessages(prev => [...prev, assistantMessage]);
        } catch (error) {
            console.error('Chat error:', error);
            const errorMessage: ChatMessage = {
                role: 'assistant',
                content: 'Sorry, I encountered an error while processing your question. Please try again.',
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div
            className="chat-popup glass"
            role="dialog"
            aria-modal="true"
            aria-labelledby="chat-title"
        >
            <div className="chat-popup-header">
                <div className="chat-popup-title">
                    <div>
                        <h3 id="chat-title">💬 Chat</h3>
                        <p className="episode-context">{episode.episode_title}</p>
                    </div>
                </div>
                <button className="close-button" onClick={onClose} aria-label="Close chat">✕</button>
            </div>

            <div className="chat-popup-messages">
                {messages.length === 0 ? (
                    <div className="chat-empty-state">
                        <div className="empty-icon">💭</div>
                        <p>Ask questions about this episode</p>
                        <div className="suggestion-chips">
                            <button
                                className="chip"
                                onClick={() => setInput('What are the main takeaways?')}
                            >
                                What are the main takeaways?
                            </button>
                            <button
                                className="chip"
                                onClick={() => setInput('Summarize the key points')}
                            >
                                Summarize the key points
                            </button>
                        </div>
                    </div>
                ) : (
                    <>
                        {messages.map((message, index) => (
                            <MessageBubble key={index} message={message} />
                        ))}
                    </>
                )}

                {isLoading && (
                    <div className="typing-indicator">
                        <div className="avatar assistant">🤖</div>
                        <div className="typing-bubble glass">
                            <div className="loading-dots">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            <div className="chat-popup-input">
                <textarea
                    className="chat-input input"
                    placeholder="Ask about this episode..."
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    rows={1}
                    disabled={isLoading}
                    aria-label="Ask a question about this episode"
                />
                <button
                    className="send-button btn-primary"
                    onClick={handleSend}
                    disabled={!input.trim() || isLoading}
                    aria-label={isLoading ? 'Sending message' : 'Send message'}
                >
                    {isLoading ? '⏳' : '🚀'}
                </button>
            </div>
        </div>
    );
}

export default ChatPopup;
