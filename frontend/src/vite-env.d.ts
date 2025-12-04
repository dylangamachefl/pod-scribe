/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_API_URL?: string;
    readonly VITE_RAG_API_URL?: string;
    readonly VITE_TRANSCRIPTION_API_URL?: string;
    readonly VITE_USE_MOCK_API?: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}
