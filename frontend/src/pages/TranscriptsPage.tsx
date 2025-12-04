import { useState, useEffect } from 'react';
import { transcriptionApi } from '../api';
import type { PodcastInfo, EpisodeInfo, TranscriptResponse } from '../api/types';
import './TranscriptsPage.css';

function TranscriptsPage() {
    const [podcasts, setPodcasts] = useState<PodcastInfo[]>([]);
    const [selectedPodcast, setSelectedPodcast] = useState('');
    const [episodes, setEpisodes] = useState<EpisodeInfo[]>([]);
    const [selectedEpisode, setSelectedEpisode] = useState('');
    const [transcript, setTranscript] = useState<TranscriptResponse | null>(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadPodcasts();
    }, []);

    const loadPodcasts = async () => {
        try {
            const data = await transcriptionApi.getPodcasts();
            setPodcasts(data);
            setLoading(false);
        } catch (err) {
            console.error('Failed to load podcasts:', err);
            setLoading(false);
        }
    };

    const handlePodcastChange = async (podcastName: string) => {
        setSelectedPodcast(podcastName);
        setSelectedEpisode('');
        setTranscript(null);

        if (podcastName) {
            try {
                const data = await transcriptionApi.getPodcastEpisodes(podcastName);
                setEpisodes(data);
            } catch (err) {
                console.error('Failed to load episodes:', err);
            }
        } else {
            setEpisodes([]);
        }
    };

    const handleEpisodeChange = async (episodeName: string) => {
        setSelectedEpisode(episodeName);

        if (episodeName && selectedPodcast) {
            try {
                const data = await transcriptionApi.getTranscript(selectedPodcast, episodeName);
                setTranscript(data);
            } catch (err) {
                console.error('Failed to load transcript:', err);
            }
        } else {
            setTranscript(null);
        }
    };

    const downloadTranscript = () => {
        if (!transcript) return;

        const blob = new Blob([transcript.content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${transcript.episode_name}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };

    const highlightText = (text: string) => {
        if (!searchTerm) return text;

        const parts = text.split(new RegExp(`(${searchTerm})`, 'gi'));
        return parts.map((part, index) =>
            part.toLowerCase() === searchTerm.toLowerCase() ? (
                <mark key={index}>{part}</mark>
            ) : (
                part
            )
        );
    };

    if (loading) {
        return <div className="transcripts-page loading">Loading transcripts...</div>;
    }

    return (
        <div className="transcripts-page">
            <div className="page-header">
                <h1>📄 Transcripts</h1>
                <p>Browse and search your podcast transcripts</p>
            </div>

            {podcasts.length === 0 ? (
                <div className="empty-state">
                    No transcripts available yet. Add feeds and run the transcription pipeline!
                </div>
            ) : (
                <>
                    <div className="selectors">
                        <div className="selector-group">
                            <label>Select Podcast</label>
                            <select
                                value={selectedPodcast}
                                onChange={(e) => handlePodcastChange(e.target.value)}
                                className="selector"
                            >
                                <option value="">Choose a podcast...</option>
                                {podcasts.map((p) => (
                                    <option key={p.name} value={p.name}>
                                        {p.name} ({p.episode_count} episodes)
                                    </option>
                                ))}
                            </select>
                        </div>

                        {selectedPodcast && (
                            <div className="selector-group">
                                <label>Select Episode</label>
                                <select
                                    value={selectedEpisode}
                                    onChange={(e) => handleEpisodeChange(e.target.value)}
                                    className="selector"
                                >
                                    <option value="">Choose an episode...</option>
                                    {episodes.map((ep) => (
                                        <option key={ep.name} value={ep.name}>
                                            {ep.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}
                    </div>

                    {transcript && (
                        <div className="transcript-viewer">
                            <div className="transcript-toolbar">
                                <input
                                    type="text"
                                    placeholder="🔍 Search in transcript..."
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="search-input"
                                />
                                <button onClick={downloadTranscript} className="btn-primary">
                                    ⬇️ Download
                                </button>
                            </div>

                            <div className="transcript-content">
                                {highlightText(transcript.content)}
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}

export default TranscriptsPage;
