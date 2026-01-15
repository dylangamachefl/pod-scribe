import { useState, useCallback } from 'react';
import { ChatMessage, SourceCitation } from '../api/types';

interface UseChatStreamProps {
    episodeTitle?: string;
    initialMessages?: ChatMessage[];
}

export function useChatStream({ episodeTitle, initialMessages = [] }: UseChatStreamProps = {}) {
    const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const sendMessage = useCallback(async (content: string) => {
        if (!content.trim() || loading) return;

        const userMsg: ChatMessage = {
            role: 'user',
            content: content.trim(),
            timestamp: new Date()
        };

        setMessages(prev => [...prev, userMsg]);
        setLoading(true);
        setError(null);

        const assistantPlaceholder: ChatMessage = {
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            sources: []
        };
        setMessages(prev => [...prev, assistantPlaceholder]);

        try {
            const history = messages.map(m => ({
                role: m.role,
                content: m.content
            }));

            const API_BASE_URL = import.meta.env.VITE_RAG_API_URL || 'http://localhost:8000';

            const response = await fetch(`${API_BASE_URL}/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    question: userMsg.content,
                    episode_title: episodeTitle,
                    conversation_history: history
                }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to get stream');
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) throw new Error('No reader available');

            let accumulatedAnswer = '';
            let sources: SourceCitation[] = [];

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.trim()) continue;

                    if (line.startsWith('METADATA:')) {
                        try {
                            const metadata = JSON.parse(line.replace('METADATA:', ''));
                            sources = metadata.sources || [];
                        } catch (e) {
                            console.error('Failed to parse metadata:', e);
                        }
                    } else {
                        accumulatedAnswer += line;

                        // Update the last message
                        setMessages(prev => {
                            const newMessages = [...prev];
                            const lastMsg = newMessages[newMessages.length - 1];
                            if (lastMsg.role === 'assistant') {
                                lastMsg.content = accumulatedAnswer;
                                lastMsg.sources = sources;
                            }
                            return newMessages;
                        });
                    }
                }
            }

        } catch (err: any) {
            console.error('Chat error:', err);
            const errorMessage = err.message || 'I encountered an error finding that answer.';
            setError(errorMessage);

            setMessages(prev => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg.role === 'assistant') {
                    if (!lastMsg.content) {
                        lastMsg.content = `Error: ${errorMessage}`;
                    } else {
                        lastMsg.content += `\n\n[Display Error: ${errorMessage}]`;
                    }
                }
                return newMessages;
            });
        } finally {
            setLoading(false);
        }
    }, [messages, episodeTitle, loading]);

    return {
        messages,
        loading,
        error,
        sendMessage,
        setMessages
    };
}
