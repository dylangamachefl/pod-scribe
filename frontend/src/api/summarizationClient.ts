/**
 * Summarization API Client
 * Communicates with the Summarization Service (FastAPI backend on port 8002)
 */

import axios from 'axios';
import type { Summary } from './types';

const API_BASE_URL = import.meta.env.VITE_SUMMARIZATION_API_URL || 'http://localhost:8002';

const axiosInstance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000, // 30 second timeout
    headers: {
        'Content-Type': 'application/json',
    },
});

export interface SummarizeRequest {
    transcript_text: string;
    episode_title: string;
    podcast_name: string;
}

export interface HealthStatus {
    status: string;
    gemini_api_configured: boolean;
    model_name: string;
    file_watcher_active: boolean;
}

export const summarizationClient = {
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
     * Generate summary for a transcript (manual trigger)
     */
    async generateSummary(request: SummarizeRequest): Promise<Summary> {
        const response = await axiosInstance.post<Summary>('/summaries/generate', request);
        return response.data;
    },

    /**
     * Health check
     */
    async getHealth(): Promise<HealthStatus> {
        const response = await axiosInstance.get<HealthStatus>('/health');
        return response.data;
    },
};
