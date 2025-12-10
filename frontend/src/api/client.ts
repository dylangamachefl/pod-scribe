/**
 * Real API Client
 * Communicates with the FastAPI backend
 */

import axios from 'axios';
import type { ChatRequest, ChatResponse, Summary, HealthStatus, IngestStats } from './types';

const API_BASE_URL = import.meta.env.VITE_RAG_API_URL || 'http://localhost:8000';

const axiosInstance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 60000, // 60 second timeout for LLM generation (RAG queries can be slow)
    headers: {
        'Content-Type': 'application/json',
    },
});

export const apiClient = {
    /**
     * Send a chat question and get AI response with sources
     */
    async chat(question: string, conversationHistory?: Array<{ role: string; content: string }>): Promise<ChatResponse> {
        const payload: ChatRequest = {
            question,
            conversation_history: conversationHistory,
        };

        const response = await axiosInstance.post<ChatResponse>('/chat', payload);
        return response.data;
    },

    /**
     * Send a chat question about a specific episode
     */
    async chatWithEpisode(episodeTitle: string, question: string, conversationHistory?: Array<{ role: string; content: string }>): Promise<ChatResponse> {
        const payload = {
            question,
            episode_title: episodeTitle,
            conversation_history: conversationHistory,
        };

        const response = await axiosInstance.post<ChatResponse>('/chat', payload);
        return response.data;
    },


    /**
     * Get list of all summaries
     */
    async getSummaries(): Promise<Summary[]> {
        const response = await axiosInstance.get<Summary[]>('/summaries');
        return response.data;
    },

    /**
     * Get summary for specific episode
     */
    async getSummary(episodeTitle: string): Promise<Summary> {
        const response = await axiosInstance.get<Summary>(`/summaries/${encodeURIComponent(episodeTitle)}`);
        return response.data;
    },

    /**
     * Health check
     */
    async getHealth(): Promise<HealthStatus> {
        const response = await axiosInstance.get<HealthStatus>('/health');
        return response.data;
    },

    /**
     * Get ingestion statistics
     */
    async getIngestStats(): Promise<IngestStats> {
        const response = await axiosInstance.get<IngestStats>('/ingest/stats');
        return response.data;
    },
};
