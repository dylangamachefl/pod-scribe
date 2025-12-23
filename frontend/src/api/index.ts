/**
 * API Client Facade
 * Switches between mock and real API based on environment variable
 */

import { apiClient } from './client';
import { transcriptionClient } from './transcriptionClient';
import { summarizationClient } from './summarizationClient';

// Export the appropriate RAG client
export const api = apiClient;

// Export the appropriate transcription client
export const transcriptionApi = transcriptionClient;

// Export the summarization client (no mock version yet)
export const summarizationApi = summarizationClient;

// Export types
export * from './types';


