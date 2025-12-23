import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Clock, Calendar, Heart, Download, FileText, PlayCircle } from 'lucide-react';
import { summarizationApi, transcriptionApi } from '../api';
import { Summary } from '../api/types';
import './EpisodeExecBrief.css';

export default function EpisodeExecBrief() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [summary, setSummary] = useState<Summary | null>(null);
    const [loading, setLoading] = useState(true);
    const [isFavorite, setIsFavorite] = useState(false);

    useEffect(() => {
        const loadBrief = async () => {
            if (!id) return;
            try {
                // In a real app we'd fetch by ID. 
                // For now, fetching all and filtering is the only option in our mock-ish API structure 
                // unless we add a specific getSummaryById endpoint.
                const summaries = await summarizationApi.getSummaries();
                const found = summaries.find(s => s.episode_title === decodeURIComponent(id)) || summaries[0];
                setSummary(found);
                setIsFavorite(found?.is_favorite || false);
            } catch (error) {
                console.error('Failed to load brief:', error);
            } finally {
                setLoading(false);
            }
        };
        loadBrief();
    }, [id]);

    const toggleFavorite = async () => {
        if (!summary || !summary.episode_id) return;
        try {
            const newStatus = !isFavorite;
            await transcriptionApi.toggleFavorite(summary.episode_id, newStatus);
            setIsFavorite(newStatus);
            summary.is_favorite = newStatus;
        } catch (err) {
            console.error('Failed to toggle favorite:', err);
        }
    };

    const downloadTranscript = () => {
        if (!summary) return;
        const url = transcriptionApi.getTranscriptUrl(
            summary.podcast_name,
            summary.episode_id || summary.episode_title
        );

        const a = document.createElement('a');
        a.href = url;
        a.download = `${summary.episode_title} - Transcript.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    const downloadSummary = () => {
        if (!summary) return;

        let content = `EPISODE BRIEF: ${summary.episode_title}\n`;
        content += `PODCAST: ${summary.podcast_name}\n`;
        content += `DATE: ${new Date(summary.created_at).toLocaleDateString()}\n`;
        content += `\nTHE HOOK:\n"${summary.hook}"\n`;

        content += `\nKEY TAKEAWAYS:\n`;
        (summary.key_takeaways || []).forEach((t, i) => {
            content += `${i + 1}. ${t.concept}: ${t.explanation}\n`;
        });

        content += `\nACTIONABLE ADVICE:\n`;
        (summary.actionable_advice || []).forEach((advice) => {
            content += `- ${advice}\n`;
        });

        content += `\nCORE CONCEPTS:\n`;
        (summary.concepts || []).forEach(c => {
            content += `- ${c.term}: ${c.definition}\n`;
        });

        if (summary.perspectives) {
            content += `\nPERSPECTIVES:\n${summary.perspectives}\n`;
        }

        content += `\nSUMMARY:\n${summary.summary}\n`;

        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${summary.episode_title} - Smart Summary.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    if (loading) return <div className="p-12 text-center text-slate-400">Loading brief...</div>;
    if (!summary) return <div className="p-12 text-center text-slate-400">Brief not found.</div>;

    return (
        <div className="exec-brief-container">
            <button className="back-nav glass-btn" onClick={() => navigate(-1)}>
                <ArrowLeft size={20} />
                <span>Back to Library</span>
            </button>

            <header className="brief-hero">
                <div className="hero-content">
                    <div className="podcast-pill">{summary.podcast_name}</div>
                    <h1 className="hero-title">{summary.episode_title}</h1>
                    <div className="hero-meta">
                        <span className="flex items-center gap-2"><Calendar size={14} /> {new Date(summary.created_at).toLocaleDateString()}</span>
                        <span className="flex items-center gap-2"><Clock size={14} /> 45 min</span>
                    </div>
                </div>
                <div className="hero-actions">
                    <button className="action-btn primary"><PlayCircle size={20} /> Play Episode</button>
                    <button
                        className={`action-btn icon-only ${isFavorite ? 'favorite-active' : ''}`}
                        onClick={toggleFavorite}
                        title={isFavorite ? "Remove from Favorites" : "Add to Favorites"}
                    >
                        <Heart size={20} fill={isFavorite ? "currentColor" : "none"} />
                    </button>
                    <button className="action-btn" onClick={downloadTranscript} title="Download Transcript">
                        <FileText size={20} />
                        <span>Transcript</span>
                    </button>
                    <button className="action-btn" onClick={downloadSummary} title="Download Summary">
                        <Download size={20} />
                        <span>Summary</span>
                    </button>
                </div>
            </header>

            <div className="bento-grid">
                {/* 1. The Hook - Prime Real Estate */}
                <div className="bento-card hook-card">
                    <h3 className="card-label">The Hook</h3>
                    <p className="hook-text">"{summary.hook}"</p>
                </div>

                {/* 2. Key Takeaways - List */}
                <div className="bento-card takeaways-card">
                    <h3 className="card-label">Key Takeaways</h3>
                    <ul className="takeaways-list">
                        {(summary.key_takeaways || []).map((item, i) => (
                            <li key={i}>
                                <span className="bullet">0{i + 1}</span>
                                <div>
                                    <span className="font-bold block text-slate-200">{item.concept}</span>
                                    <span className="text-sm">{item.explanation}</span>
                                </div>
                            </li>
                        ))}
                    </ul>
                </div>

                {/* 3. Concepts - Tags/Cloud */}
                <div className="bento-card concepts-card">
                    <h3 className="card-label">Core Concepts</h3>
                    <div className="concepts-cloud">
                        {(summary.concepts || []).map(c => (
                            <span key={c.term} className="concept-tag" title={c.definition}>{c.term}</span>
                        ))}
                    </div>
                </div>

                {/* 4. Actionable Advice - Callout */}
                <div className="bento-card action-card">
                    <h3 className="card-label">Actionable Advice</h3>
                    <div className="advice-content">
                        {(summary.actionable_advice || []).map((advice, i) => (
                            <div key={i} className="advice-item">
                                <div className="check-circle">✓</div>
                                <p>{advice}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <section className="deep-dive-section">
                <h2 className="section-title">Deep Dive</h2>
                <div className="summary-prose">
                    {summary.summary}
                </div>
            </section>
        </div>
    );
}
