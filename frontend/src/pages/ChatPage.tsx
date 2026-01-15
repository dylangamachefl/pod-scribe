import { useState, useRef, useEffect } from 'react';
import './ChatPage.css';
import MessageBubble from '../components/MessageBubble';
import { useChatStream } from '../hooks/useChatStream';

function ChatPage() {
    const [input, setInput] = useState('');
    const { messages, loading: isLoading, sendMessage } = useChatStream();
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;
        await sendMessage(input);
        setInput('');
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="chat-page">
            <div className="chat-container glass">
                <div className="chat-header">
                    <h2>Ask anything about your podcast transcripts</h2>
                    <p className="subtitle">
                        Powered by RAG + Gemini AI • {import.meta.env.VITE_USE_MOCK_API === 'true' ? '🟡 Mock Mode' : '🟢 Live'}
                    </p>
                </div>

                <div className="messages-container">
                    {messages.length === 0 ? (
                        <div className="empty-state">
                            <div className="empty-icon">💭</div>
                            <h3>Start a conversation</h3>
                            <p>Ask questions about topics, speakers, or specific episodes</p>
                            <div className="suggestion-chips">
                                <button
                                    className="chip"
                                    onClick={() => setInput('What breathing techniques were discussed?')}
                                >
                                    What breathing techniques were discussed?
                                </button>
                                <button
                                    className="chip"
                                    onClick={() => setInput('Tell me about red light therapy')}
                                >
                                    Tell me about red light therapy
                                </button>
                                <button
                                    className="chip"
                                    onClick={() => setInput('What did they say about stress reduction?')}
                                >
                                    What did they say about stress reduction?
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

                <div className="chat-input-container">
                    <textarea
                        className="chat-input input"
                        placeholder="Ask a question about your podcasts..."
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
                        {isLoading ? '⏳' : '🚀'} Send
                    </button>
                </div>
            </div>
        </div>
    );
}

export default ChatPage;
