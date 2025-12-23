/**
 * API Type Definitions
 */

export interface SourceCitation {
    podcast_name: string;
    episode_title: string;
    speaker: string;
    timestamp: string;
    text_snippet: string;
    relevance_score: number;
}

export interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    sources?: SourceCitation[];
    timestamp?: Date;
}

export interface ChatRequest {
    question: string;
    conversation_history?: Array<{ role: string; content: string }>;
}

export interface ChatResponse {
    answer: string;
    sources: SourceCitation[];
    processing_time_ms: number;
}

export interface Summary {
    episode_title: string;
    podcast_name: string;
    summary: string;
    key_topics: string[];
    speakers: string[];
    duration?: string;
    audio_url?: string;
    created_at: string;
    source_file?: string; // Path to original transcript file
    // Structured summary fields (from Gemini)
    hook?: string;
    key_takeaways?: Array<{ concept: string; explanation: string }>;
    actionable_advice?: string[];
    quotes?: string[];
    concepts?: Array<{ term: string; definition: string }>;
    perspectives?: string;

    // Association fields
    episode_id?: string;
    is_favorite?: boolean;

    // Two-stage pipeline metadata
    stage1_processing_time_ms?: number;
    stage2_processing_time_ms?: number;
    total_processing_time_ms?: number;
}


export interface HealthStatus {
    status: string;
    qdrant_connected: boolean;
    embedding_model_loaded: boolean;
    gemini_api_configured: boolean;
}

export interface IngestStats {
    total_chunks: number;
    collection_name: string;
    embedding_dimension: number;
}

// ============================================================================
// Transcription Service Types
// ============================================================================

export interface Feed {
    id: string;
    url: string;
    title: string;
    active: boolean;
}

export interface FeedCreate {
    url: string;
}

export interface FeedUpdate {
    active: boolean;
}

export interface Episode {
    id: string;
    episode_title: string;
    feed_title: string;
    published_date: string;
    duration?: string;
    audio_url: string;
    selected: boolean;
    status: string;
    fetched_date?: string;
    is_seen: boolean;
    is_favorite: boolean;
    feed_url?: string;
}

export interface EpisodeSelect {
    selected: boolean;
}

export interface BulkSelectRequest {
    episode_ids: string[];
    selected: boolean;
}

export interface BulkSeenRequest {
    episode_ids: string[];
    seen: boolean;
}

export interface TranscriptionStatus {
    is_running: boolean;
    current_episode?: string;
    current_podcast?: string;
    stage: string;
    progress: number;
    episodes_completed: number;
    episodes_total: number;
    gpu_name?: string;
    gpu_usage: number;
    vram_used_gb: number;
    vram_total_gb: number;
    start_time?: string;
    recent_logs?: string[];
}

export interface TranscriptionStartRequest {
    episode_ids?: string[];
}

export interface TranscriptionStartResponse {
    status: string;
    message: string;
    episodes_count: number;
}

export interface PodcastInfo {
    name: string;
    episode_count: number;
}

export interface EpisodeInfo {
    name: string;
    file_path: string;
}

export interface TranscriptResponse {
    podcast_name: string;
    episode_name: string;
    content: string;
}

export interface TranscriptionStats {
    active_feeds: number;
    total_feeds: number;
    total_podcasts: number;
    total_episodes_processed: number;
    pending_episodes: number;
    selected_episodes: number;
}

export interface TranscriptionHealth {
    status: string;
    api_version: string;
    transcription_service_available: boolean;
}

