/**
 * Mock Transcription Service API Client for Development
 * Returns realistic mock data without backend dependency
 */

import type {
    Feed,
    FeedCreate,
    FeedUpdate,
    Episode,
    TranscriptionStatus,
    TranscriptionStartRequest,
    TranscriptionStartResponse,
    PodcastInfo,
    EpisodeInfo,
    TranscriptionStats,
    TranscriptionHealth,
} from './types';

// Simulated delay to mimic API latency
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Mock state management
let mockFeeds: Feed[] = [
    {
        id: '1',
        url: 'https://feeds.megaphone.fm/hubermanlab',
        title: 'Huberman Lab',
        active: true,
    },
    {
        id: '2',
        url: 'https://lexfridman.com/feed/podcast/',
        title: 'Lex Fridman Podcast',
        active: true,
    },
    {
        id: '3',
        url: 'https://feeds.simplecast.com/54nAGcIl',
        title: 'The Tim Ferriss Show',
        active: false,
    },
];

let mockEpisodes: Episode[] = [
    {
        id: 'ep1',
        episode_title: 'Dr. Peter Attia: Supplements for Longevity & Their Efficacy',
        feed_title: 'Huberman Lab',
        published_date: '2024-12-01T10:00:00Z',
        duration: '2:15:30',
        audio_url: 'https://example.com/episode1.mp3',
        selected: true,
        status: 'pending',
    },
    {
        id: 'ep2',
        episode_title: 'Dr. Tim Ferriss: How to Learn Better & Create Your Best Future',
        feed_title: 'Huberman Lab',
        published_date: '2024-11-28T10:00:00Z',
        duration: '2:45:20',
        audio_url: 'https://example.com/episode2.mp3',
        selected: true,
        status: 'pending',
    },
    {
        id: 'ep3',
        episode_title: 'Sam Harris: The Multiverse & You',
        feed_title: 'Lex Fridman Podcast',
        published_date: '2024-11-30T15:00:00Z',
        duration: '3:05:15',
        audio_url: 'https://example.com/episode3.mp3',
        selected: false,
        status: 'pending',
    },
    {
        id: 'ep4',
        episode_title: 'Yann LeCun: Meta AI, Open Source, & AGI',
        feed_title: 'Lex Fridman Podcast',
        published_date: '2024-11-25T15:00:00Z',
        duration: '4:12:45',
        audio_url: 'https://example.com/episode4.mp3',
        selected: false,
        status: 'pending',
    },
];

let mockTranscriptionRunning = false;
let mockTranscriptionProgress = 0;

const MOCK_PODCASTS: PodcastInfo[] = [
    { name: 'Huberman Lab', episode_count: 12 },
    { name: 'Lex Fridman Podcast', episode_count: 8 },
    { name: 'The Tim Ferriss Show', episode_count: 5 },
];

const MOCK_TRANSCRIPT_CONTENT = `[00:00:15] Dr. Andrew Huberman: Welcome to the Huberman Lab Podcast, where we discuss science and science-based tools for everyday life. I'm Andrew Huberman, and I'm a professor of neurobiology and ophthalmology at Stanford School of Medicine.

[00:00:45] Today we're discussing breathing techniques and their impact on mental and physical performance. We'll cover the science of respiration, the autonomic nervous system, and practical protocols you can use immediately.

[00:05:30] The physiological sigh is one of the fastest ways to reduce stress in real-time. It involves two quick inhales through the nose followed by a long exhale through the mouth. This pattern was discovered by physiologists at Stanford and UCLA.

[00:08:15] Dr. Jack Feldman: What we found is that the physiological sigh occurs spontaneously throughout the day and night. It's a pattern that helps re-inflate the alveoli in the lungs that have collapsed during normal breathing.

[00:12:45] Dr. Andrew Huberman: Just one or two physiological sighs can significantly calm the nervous system within seconds, making it incredibly useful during moments of acute stress or before important events.

[00:15:30] Box breathing is another powerful technique. It involves inhaling for 4 counts, holding for 4, exhaling for 4, and holding again for 4. This creates a square or "box" pattern, hence the name.

[00:20:00] Dr. Jack Feldman: The beauty of breathing techniques is that they're portable, free, and can be done anywhere. They directly influence the brainstem nuclei that control arousal and calmness.

[00:25:15] Dr. Andrew Huberman: For those interested in performance enhancement, certain breathing patterns can increase alertness and focus. Rapid inhales with brief exhales can activate the sympathetic nervous system.

[00:30:45] However, it's important to use the right breathing technique for the right context. Pre-sleep breathing should be slow and emphasize long exhales to activate parasympathetic tone.

[00:35:20] In summary, breathing is far more than just gas exchange. It's a powerful tool for modulating your nervous system state, improving health, and optimizing performance across all domains of life.`;

export const mockTranscriptionClient = {
    // ========================================================================
    // Feed Management
    // ========================================================================

    async getFeeds(): Promise<Feed[]> {
        await delay(400);
        return [...mockFeeds];
    },

    async addFeed(feedCreate: FeedCreate): Promise<Feed> {
        await delay(600);
        const newFeed: Feed = {
            id: `feed_${Date.now()}`,
            url: feedCreate.url,
            title: `New Podcast ${mockFeeds.length + 1}`,
            active: true,
        };
        mockFeeds.push(newFeed);
        return newFeed;
    },

    async updateFeed(feedId: string, feedUpdate: FeedUpdate): Promise<Feed> {
        await delay(400);
        const feed = mockFeeds.find(f => f.id === feedId);
        if (!feed) {
            throw new Error('Feed not found');
        }
        feed.active = feedUpdate.active;
        return { ...feed };
    },

    async deleteFeed(feedId: string): Promise<void> {
        await delay(500);
        mockFeeds = mockFeeds.filter(f => f.id !== feedId);
    },

    // ========================================================================
    // Episode Queue
    // ========================================================================

    async getEpisodeQueue(): Promise<Episode[]> {
        await delay(500);
        return [...mockEpisodes];
    },

    async fetchEpisodes(): Promise<{ status: string; new_episodes: number }> {
        await delay(1500); // Simulate RSS fetch delay

        // Add a new mock episode
        const newEpisode: Episode = {
            id: `ep_${Date.now()}`,
            episode_title: 'New Episode: Mock Data Added',
            feed_title: 'Huberman Lab',
            published_date: new Date().toISOString(),
            duration: '1:30:00',
            audio_url: 'https://example.com/new-episode.mp3',
            selected: false,
            status: 'pending',
        };
        mockEpisodes.unshift(newEpisode);

        return {
            status: 'success',
            new_episodes: 1,
        };
    },

    async selectEpisode(episodeId: string, selected: boolean): Promise<void> {
        await delay(200);
        const episode = mockEpisodes.find(e => e.id === episodeId);
        if (episode) {
            episode.selected = selected;
        }
    },

    async bulkSelectEpisodes(episodeIds: string[], selected: boolean): Promise<void> {
        await delay(300);
        episodeIds.forEach(id => {
            const episode = mockEpisodes.find(e => e.id === id);
            if (episode) {
                episode.selected = selected;
            }
        });
    },

    async clearProcessedEpisodes(): Promise<{ status: string; count: number }> {
        await delay(400);
        const processedCount = mockEpisodes.filter(e => e.status === 'completed').length;
        mockEpisodes = mockEpisodes.filter(e => e.status !== 'completed');
        return {
            status: 'success',
            count: processedCount,
        };
    },

    // ========================================================================
    // Transcription Control
    // ========================================================================

    async getTranscriptionStatus(): Promise<TranscriptionStatus> {
        await delay(300);

        if (mockTranscriptionRunning) {
            // Simulate progress
            mockTranscriptionProgress = Math.min(mockTranscriptionProgress + 5, 95);

            return {
                is_running: true,
                current_episode: 'Dr. Peter Attia: Supplements for Longevity & Their Efficacy',
                current_podcast: 'Huberman Lab',
                stage: 'transcribing',
                progress: mockTranscriptionProgress,
                episodes_completed: 0,
                episodes_total: 2,
                gpu_name: 'NVIDIA GeForce RTX 3070',
                gpu_usage: 85.5,
                vram_used_gb: 6.2,
                vram_total_gb: 8.0,
                start_time: new Date(Date.now() - 1000 * 60 * 15).toISOString(), // 15 min ago
            };
        }

        return {
            is_running: false,
            stage: 'idle',
            progress: 0,
            episodes_completed: 0,
            episodes_total: 0,
            gpu_name: 'NVIDIA GeForce RTX 3070',
            gpu_usage: 0,
            vram_used_gb: 0,
            vram_total_gb: 8.0,
        };
    },

    async startTranscription(
        _request?: TranscriptionStartRequest
    ): Promise<TranscriptionStartResponse> {
        await delay(800);

        const selectedEpisodes = mockEpisodes.filter(e => e.selected);
        mockTranscriptionRunning = true;
        mockTranscriptionProgress = 10;

        // Simulate marking episodes as processing
        selectedEpisodes.forEach(ep => {
            ep.status = 'processing';
        });

        return {
            status: 'started',
            message: 'Transcription started successfully (mock)',
            episodes_count: selectedEpisodes.length,
        };
    },

    // ========================================================================
    // Transcript Browsing
    // ========================================================================

    async getPodcasts(): Promise<PodcastInfo[]> {
        await delay(400);
        return [...MOCK_PODCASTS];
    },

    async getPodcastEpisodes(podcastName: string): Promise<EpisodeInfo[]> {
        await delay(500);

        const episodes: EpisodeInfo[] = [
            {
                name: 'Essentials: Breathing for Mental & Physical Health',
                file_path: `/transcripts/${podcastName}/episode1.txt`,
            },
            {
                name: 'Using Red Light to Improve Metabolism',
                file_path: `/transcripts/${podcastName}/episode2.txt`,
            },
            {
                name: 'Dr. Peter Attia: Supplements for Longevity',
                file_path: `/transcripts/${podcastName}/episode3.txt`,
            },
        ];

        return episodes;
    },

    async getTranscript(podcastName: string, episodeName: string): Promise<{ content: string; podcast_name: string; episode_name: string }> {
        await delay(600);

        return {
            podcast_name: podcastName,
            episode_name: episodeName,
            content: MOCK_TRANSCRIPT_CONTENT,
        };
    },

    getTranscriptUrl(podcastName: string, episodeName: string): string {
        return `mock://transcripts/${encodeURIComponent(podcastName)}/${encodeURIComponent(episodeName)}.txt`;
    },

    // ========================================================================
    // Stats & Health
    // ========================================================================

    async getStats(): Promise<TranscriptionStats> {
        await delay(350);

        return {
            active_feeds: mockFeeds.filter(f => f.active).length,
            total_feeds: mockFeeds.length,
            total_podcasts: MOCK_PODCASTS.length,
            total_episodes_processed: 25,
            pending_episodes: mockEpisodes.filter(e => e.status === 'pending').length,
            selected_episodes: mockEpisodes.filter(e => e.selected).length,
        };
    },

    async getHealth(): Promise<TranscriptionHealth> {
        await delay(250);

        return {
            status: 'healthy (mock)',
            api_version: '1.0.0-mock',
            transcription_service_available: true,
        };
    },
};
