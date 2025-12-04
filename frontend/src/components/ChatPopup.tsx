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
    const [position, setPosition] = useState({ x: window.innerWidth - 420, y: 100 });
    const [isDragging, setIsDragging] = useState(false);
    const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const popupRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleMouseDown = (e: React.MouseEvent) => {
        if ((e.target as HTMLElement).closest('.chat-popup-header')) {
            setIsDragging(true);
            setDragOffset({
                x: e.clientX - position.x,
                y: e.clientY - position.y,
            });
        }
    };

    useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (isDragging) {
                setPosition({
                    x: e.clientX - dragOffset.x,
                    y: e.clientY - dragOffset.y,
                });
            }
        };

        const handleMouseUp = () => {
            setIsDragging(false);
        };

        if (isDragging) {
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
        }

        return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isDragging, dragOffset]);

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
            ref={popupRef}
            className="chat-popup glass"
            style={{
                left: `${position.x}px`,
                top: `${position.y}px`,
            }}
            onMouseDown={handleMouseDown}
        >
            <div className="chat-popup-header">
                <div className="chat-popup-title">
                    <span className="drag-indicator">⋮⋮</span>
                    <div>
                        <h3>💬 Chat</h3>
                        <p className="episode-context">{episode.episode_title}</p>
                    </div>
                </div>
                <button className="close-button" onClick={onClose}>✕</button>
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
                />
                <button
                    className="send-button btn-primary"
                    onClick={handleSend}
                    disabled={!input.trim() || isLoading}
                >
                    {isLoading ? '⏳' : '🚀'}
                </button>
            </div>
        </div>
    );
}

export default ChatPopup;
