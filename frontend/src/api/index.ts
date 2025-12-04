/**
 * API Client Facade
 * Switches between mock and real API based on environment variable
 */

import { mockApiClient } from './mockClient';
import { mockTranscriptionClient } from './mockTranscriptionClient';
import { apiClient } from './client';
import { transcriptionClient } from './transcriptionClient';

// Check if we should use mock API
const USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true';

// Export the appropriate RAG client
export const api = USE_MOCK ? mockApiClient : apiClient;

// Export the appropriate transcription client
export const transcriptionApi = USE_MOCK ? mockTranscriptionClient : transcriptionClient;

// Export types
export * from './types';


