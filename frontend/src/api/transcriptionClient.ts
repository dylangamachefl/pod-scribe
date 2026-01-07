/**
 * Transcription Service API Client
 * Communicates with the Transcription FastAPI backend
 */

import axios from 'axios';
import type {
    Feed,
    FeedCreate,
    FeedUpdate,
    Episode,
    EpisodeSelect,
    BulkSelectRequest,
    BulkSeenRequest,
    TranscriptionStatus,
    TranscriptionStartRequest,
    TranscriptionStartResponse,
    PodcastInfo,
    EpisodeInfo,
    TranscriptionStats,
    TranscriptionHealth,
    BatchProgressResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_TRANSCRIPTION_API_URL || 'http://localhost:8001';

const axiosInstance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 120000, // 2 minute timeout for transcription operations
    headers: {
        'Content-Type': 'application/json',
    },
});

export const transcriptionClient = {
    // ========================================================================
    // Feed Management
    // ========================================================================

    /**
     * Get all RSS feed subscriptions
     */
    async getFeeds(): Promise<Feed[]> {
        const response = await axiosInstance.get<Feed[]>('/feeds');
        return response.data;
    },

    /**
     * Add new RSS feed
     */
    async addFeed(feedCreate: FeedCreate): Promise<Feed> {
        const response = await axiosInstance.post<Feed>('/feeds', feedCreate);
        return response.data;
    },

    /**
     * Update feed (toggle active state)
     */
    async updateFeed(feedId: string, feedUpdate: FeedUpdate): Promise<Feed> {
        const response = await axiosInstance.put<Feed>(`/feeds/${feedId}`, feedUpdate);
        return response.data;
    },

    /**
     * Delete RSS feed
     */
    async deleteFeed(feedId: string): Promise<void> {
        await axiosInstance.delete(`/feeds/${feedId}`);
    },

    // ========================================================================
    // Episode Queue
    // ========================================================================

    /**
     * Get all pending episodes in queue
     */
    async getEpisodeQueue(): Promise<Episode[]> {
        const response = await axiosInstance.get<Episode[]>('/episodes/queue');
        return response.data;
    },

    /**
     * Get all episodes with optional filtering
     */
    async getAllEpisodes(params?: { status?: string; feed_title?: string }): Promise<Episode[]> {
        const response = await axiosInstance.get<Episode[]>('/episodes', { params });
        return response.data;
    },

    /**
     * Fetch new episodes from active feeds
     */
    async fetchEpisodes(days?: number): Promise<{ status: string; new_episodes: number }> {
        const response = await axiosInstance.post<{ status: string; new_episodes: number }>(
            '/episodes/fetch',
            days !== undefined ? { days } : undefined
        );
        return response.data;
    },

    /**
     * Select/deselect an episode
     */
    async selectEpisode(episodeId: string, selected: boolean): Promise<void> {
        await axiosInstance.put(`/episodes/${episodeId}/select`, {
            selected,
        } as EpisodeSelect);
    },

    /**
     * Bulk select/deselect episodes
     */
    async bulkSelectEpisodes(episodeIds: string[], selected: boolean): Promise<void> {
        await axiosInstance.post('/episodes/bulk-select', {
            episode_ids: episodeIds,
            selected,
        } as BulkSelectRequest);
    },

    /**
     * Bulk mark episodes as seen/unseen
     */
    async bulkSeenEpisodes(episodeIds: string[], seen: boolean): Promise<void> {
        await axiosInstance.post('/episodes/bulk-seen', {
            episode_ids: episodeIds,
            seen,
        } as BulkSeenRequest);
    },

    /**
     * Toggle favorite status
     */
    async toggleFavorite(episodeId: string, is_favorite: boolean): Promise<void> {
        await axiosInstance.put(`/episodes/${episodeId}/favorite`, {
            is_favorite,
        });
    },

    /**
     * Clear processed episodes from queue
     */
    async clearProcessedEpisodes(): Promise<{ status: string; count: number }> {
        const response = await axiosInstance.delete<{ status: string; count: number }>(
            '/episodes/processed'
        );
        return response.data;
    },

    // ========================================================================
    // Transcription Control
    // ========================================================================

    /**
     * Get current transcription status
     */
    async getTranscriptionStatus(): Promise<TranscriptionStatus> {
        const response = await axiosInstance.get<TranscriptionStatus>('/transcription/status');
        return response.data;
    },

    /**
     * Start transcription for selected episodes
     */
    async startTranscription(
        request?: TranscriptionStartRequest
    ): Promise<TranscriptionStartResponse> {
        const response = await axiosInstance.post<TranscriptionStartResponse>(
            '/transcription/start',
            request || {}
        );
        return response.data;
    },

    /**
     * Manually clear all stale pipeline status and stats
     */
    async clearTranscriptionStatus(): Promise<{ status: string; message: string }> {
        const response = await axiosInstance.post<{ status: string; message: string }>(
            '/transcription/status/clear'
        );
        return response.data;
    },

    /**
     * Get detailed progress for a specific batch
     */
    async getBatchProgress(batchId: string): Promise<BatchProgressResponse> {
        const response = await axiosInstance.get<BatchProgressResponse>(`/batches/${batchId}/progress`);
        return response.data;
    },

    // ========================================================================
    // Transcript Browsing
    // ========================================================================

    /**
     * List all available podcasts
     */
    async getPodcasts(): Promise<PodcastInfo[]> {
        const response = await axiosInstance.get<PodcastInfo[]>('/transcripts');
        return response.data;
    },

    /**
     * List episodes for a specific podcast
     */
    async getPodcastEpisodes(podcastName: string): Promise<EpisodeInfo[]> {
        const response = await axiosInstance.get<EpisodeInfo[]>(
            `/transcripts/${encodeURIComponent(podcastName)}`
        );
        return response.data;
    },

    /**
     * Get specific transcript content
     */
    /**
     * Get specific transcript content (raw text)
     */
    async getTranscript(podcastName: string, episodeName: string): Promise<{ content: string; podcast_name: string; episode_name: string }> {
        // Fetch raw text from static file endpoint
        const response = await axiosInstance.get<string>(
            `/files/${encodeURIComponent(podcastName)}/${encodeURIComponent(episodeName)}.txt`,
            { transformResponse: [(data) => data] } // Prevent JSON parsing
        );

        return {
            content: response.data,
            podcast_name: podcastName,
            episode_name: episodeName
        };
    },

    /**
     * Get URL for direct download
     */
    getTranscriptUrl(podcastName: string, episodeId: string): string {
        return `${API_BASE_URL}/transcripts/${encodeURIComponent(podcastName)}/${encodeURIComponent(episodeId)}/download`;
    },

    // ========================================================================
    // Stats & Health
    // ========================================================================

    /**
     * Get overall statistics
     */
    async getStats(): Promise<TranscriptionStats> {
        const response = await axiosInstance.get<TranscriptionStats>('/stats');
        return response.data;
    },

    /**
     * Health check
     */
    async getHealth(): Promise<TranscriptionHealth> {
        const response = await axiosInstance.get<TranscriptionHealth>('/health');
        return response.data;
    },
};
