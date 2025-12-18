import { useState, useRef, useEffect } from 'react';
import { X, Send, Sparkles } from 'lucide-react';
import { apiClient } from '../api/client';
import { ChatMessage } from '../api/types';
import './ChatDrawer.css';

interface ChatDrawerProps {
    isOpen: boolean;
    onClose: () => void;
    initialContext?: {
        type: 'library' | 'episode';
        id?: string;
        title?: string;
    }
}

export function ChatDrawer({ isOpen, onClose, initialContext }: ChatDrawerProps) {
    const [messages, setMessages] = useState<ChatMessage[]>([{
        role: 'assistant',
        content: 'Hi! I can help you find insights across your podcast library. What would you like to know?',
        timestamp: new Date()
    }]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        if (isOpen) {
            scrollToBottom();
        }
    }, [messages, isOpen]);

    const handleSend = async () => {
        if (!input.trim() || loading) return;

        const userMsg: ChatMessage = {
            role: 'user',
            content: input.trim(),
            timestamp: new Date()
        };

        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        try {
            // Prepare history for API
            const history = messages.map(m => ({
                role: m.role,
                content: m.content
            }));

            // TODO: If initialContext is 'episode', we should modify the prompt or use a different endpoint
            // For now we use the generic chat endpoint
            const response = await apiClient.chat(userMsg.content, history);

            const aiMsg: ChatMessage = {
                role: 'assistant',
                content: response.answer,
                sources: response.sources,
                timestamp: new Date()
            };

            setMessages(prev => [...prev, aiMsg]);
        } catch (error) {
            console.error('Chat error:', error);
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: 'Sorry, I encountered an error finding that answer. Please try again.',
                timestamp: new Date()
            }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            {isOpen && <div className="drawer-overlay" onClick={onClose} />}
            <div className={`chat-drawer glass ${isOpen ? 'open' : ''}`}>
                <div className="drawer-header">
                    <div className="header-title">
                        <Sparkles size={20} className="text-purple-400" />
                        <span>AI Assistant</span>
                    </div>
                    {initialContext?.title && (
                        <div className="context-badge">
                            Context: {initialContext.title}
                        </div>
                    )}
                    <button className="close-btn" onClick={onClose}>
                        <X size={20} />
                    </button>
                </div>

                <div className="messages-area">
                    {messages.map((msg, i) => (
                        <div key={i} className={`message-wrapper ${msg.role}`}>
                            <div className="message-bubble">
                                <div className="message-content">{msg.content}</div>
                                {msg.sources && msg.sources.length > 0 && (
                                    <div className="sources-list">
                                        <div className="sources-label">Sources:</div>
                                        {msg.sources.map((source, idx) => (
                                            <div key={idx} className="source-card">
                                                <div className="source-header">
                                                    <span className="source-podcast">{source.podcast_name}</span>
                                                    <span className="source-time">{source.timestamp}</span>
                                                </div>
                                                <div className="source-episode">{source.episode_title}</div>
                                                {/* <div className="source-snippet">"{source.text_snippet}"</div> */}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                    {loading && (
                        <div className="message-wrapper assistant">
                            <div className="message-bubble loading">
                                <span className="dot"></span>
                                <span className="dot"></span>
                                <span className="dot"></span>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                <div className="input-area">
                    <div className="input-wrapper">
                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSend();
                                }
                            }}
                            placeholder="Ask me anything about your podcasts..."
                            rows={1}
                        />
                        <button
                            className="send-btn"
                            disabled={!input.trim() || loading}
                            onClick={handleSend}
                        >
                            <Send size={18} />
                        </button>
                    </div>
                    <div className="input-footer">
                        Using RAG over {initialContext?.type === 'episode' ? 'current episode' : 'entire library'}
                    </div>
                </div>
            </div>
        </>
    );
}
