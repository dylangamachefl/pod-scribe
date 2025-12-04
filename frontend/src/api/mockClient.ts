/**
 * Mock API Client for Development
 * Returns realistic mock data without backend dependency
 */

import type { ChatResponse, Summary, HealthStatus, IngestStats } from './types';

// Simulated delay to mimic API latency
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

const MOCK_SUMMARIES: Summary[] = [
    {
        episode_title: "Essentials: Breathing for Mental & Physical Health & Performance",
        podcast_name: "Huberman Lab",
        summary: "Dr. Andrew Huberman and Dr. Jack Feldman discuss the science of breathing and its profound effects on mental and physical health. They explore different breathing patterns, their impact on the nervous system, and practical techniques for improving focus, reducing stress, and enhancing athletic performance.",
        key_topics: [
            "Autonomic nervous system regulation",
            "Box breathing technique",
            "Physiological sigh for stress reduction",
            "Breathing patterns and emotions",
            "Performance optimization through breath control"
        ],
        speakers: ["Dr. Andrew Huberman", "Dr. Jack Feldman"],
        duration: "1:45:30",
        created_at: "2024-12-03 18:30:00"
    },
    {
        episode_title: "Using Red Light to Improve Metabolism & the Harmful Effects of LEDs",
        podcast_name: "Huberman Lab",
        summary: "Dr. Glen Jeffery explains how red and near-infrared light can enhance mitochondrial function and improve metabolism. The conversation covers the science of photobiomodulation, optimal timing for light exposure, and the potential negative effects of LED lighting on circadian rhythms and eye health.",
        key_topics: [
            "Mitochondrial function and red light",
            "Circadian rhythm disruption",
            "LED vs natural light",
            "Therapeutic applications of photobiomodulation",
            "Eye health and light exposure"
        ],
        speakers: ["Dr. Andrew Huberman", "Dr. Glen Jeffery"],
        duration: "2:15:45",
        created_at: "2024-12-02 14:20:00"
    }
];

const MOCK_SOURCES = [
    {
        podcast_name: "Huberman Lab",
        episode_title: "Essentials: Breathing for Mental & Physical Health & Performance",
        speaker: "Dr. Jack Feldman",
        timestamp: "00:45:23",
        text_snippet: "The physiological sigh is one of the fastest ways to reduce stress in real-time. It involves two quick inhales through the nose followed by a long exhale through the mouth.",
        relevance_score: 0.92
    },
    {
        podcast_name: "Huberman Lab",
        episode_title: "Essentials: Breathing for Mental & Physical Health & Performance",
        speaker: "Dr. Andrew Huberman",
        timestamp: "00:47:10",
        text_snippet: "Just one or two physiological sighs can significantly calm the nervous system within seconds, making it incredibly useful during moments of acute stress.",
        relevance_score: 0.88
    }
];

export const mockApiClient = {
    /**
     * Mock chat endpoint
     */
    async chat(question: string): Promise<ChatResponse> {
        await delay(1500); // Simulate API delay

        return {
            answer: `This is a mock response to your question: "${question}"\n\nBased on the podcast transcripts, ${MOCK_SOURCES[0].speaker} explains that ${MOCK_SOURCES[0].text_snippet.toLowerCase()}\n\nAdditionally, ${MOCK_SOURCES[1].speaker} mentions that ${MOCK_SOURCES[1].text_snippet.toLowerCase()}\n\nThis mock response demonstrates how the actual RAG system will retrieve relevant context from transcripts and generate comprehensive answers using the Gemini API.`,
            sources: MOCK_SOURCES,
            processing_time_ms: 1247
        };
    },

    /**
     * Mock episode-specific chat endpoint
     */
    async chatWithEpisode(episodeTitle: string, question: string): Promise<ChatResponse> {
        await delay(1500);

        const episodeSource = MOCK_SOURCES.find(s => s.episode_title === episodeTitle) || MOCK_SOURCES[0];

        return {
            answer: `This is a mock response about "${episodeTitle}" to your question: "${question}"\n\nFrom this specific episode, ${episodeSource.speaker} explains: ${episodeSource.text_snippet}\n\nThis demonstrates episode-scoped chat with full transcript context.`,
            sources: [episodeSource],
            processing_time_ms: 1150
        };
    },

    /**
     * Mock summaries list endpoint
     */
    async getSummaries(): Promise<Summary[]> {
        await delay(500);
        return MOCK_SUMMARIES;
    },

    /**
     * Mock health check endpoint
     */
    async getHealth(): Promise<HealthStatus> {
        await delay(200);
        return {
            status: "healthy (mock)",
            qdrant_connected: true,
            embedding_model_loaded: true,
            gemini_api_configured: true
        };
    },

    /**
     * Mock ingest stats endpoint
     */
    async getIngestStats(): Promise<IngestStats> {
        await delay(300);
        return {
            total_chunks: 1247,
            collection_name: "podcast_transcripts",
            embedding_dimension: 384
        };
    }
};
