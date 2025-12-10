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

/**
 * Parse structured summary from JSON string if present
 */
function parseStructuredSummary(summary: Summary): Summary {
    // Check if summary field contains JSON-wrapped structured data
    if (typeof summary.summary === 'string' && summary.summary.includes('```json')) {
        try {
            // Remove markdown code fences
            let cleaned = summary.summary.trim();
            if (cleaned.startsWith('```json')) {
                cleaned = cleaned.substring(7); // Remove ```json
            } else if (cleaned.startsWith('```')) {
                cleaned = cleaned.substring(3); // Remove ```
            }
            if (cleaned.endsWith('```')) {
                cleaned = cleaned.substring(0, cleaned.length - 3);
            }
            cleaned = cleaned.trim();

            // Parse the JSON
            const structured = JSON.parse(cleaned);

            // Extract structured fields
            return {
                ...summary,
                hook: structured.hook,
                key_takeaways: structured.key_takeaways,
                actionable_advice: structured.actionable_advice,
                quotes: structured.quotes,
                concepts: structured.concepts,
                perspectives: structured.perspectives,
                // Use the plain text summary from structured data if available
                summary: structured.summary || summary.summary,
                // Use key_topics from structured data if available
                key_topics: structured.key_topics || summary.key_topics || [],
            };
        } catch (e) {
            console.warn('Failed to parse structured summary:', e);
            return summary;
        }
    }
    return summary;
}

export const summarizationClient = {
    /**
     * Get list of all summaries
     */
    async getSummaries(): Promise<Summary[]> {
        const response = await axiosInstance.get<Summary[]>('/summaries');
        // Parse structured summaries
        return response.data.map(parseStructuredSummary);
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
