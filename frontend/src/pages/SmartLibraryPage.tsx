import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { summarizationApi } from '../api';
import { Summary } from '../api/types';
import { SmartCard } from '../components/SmartCard';
import { ChatDrawer } from '../components/ChatDrawer';
import { Search, Filter, Radio, X } from 'lucide-react';
import './SmartLibraryPage.css';

export default function SmartLibraryPage() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const tagFilter = searchParams.get('tag');
    const feedFilter = searchParams.get('feed');

    const [summaries, setSummaries] = useState<Summary[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');

    // Chat & Detail States
    const [chatContext, setChatContext] = useState<{ type: 'episode', title: string } | null>(null);
    const [isChatOpen, setIsChatOpen] = useState(false);

    useEffect(() => {
        const loadSummaries = async () => {
            setLoading(true);
            try {
                const data = await summarizationApi.getSummaries();
                setSummaries(data);
            } catch (error) {
                console.error('Failed to load library:', error);
            } finally {
                setLoading(false);
            }
        };
        loadSummaries();
    }, []);

    const handleChat = (summary: Summary) => {
        setChatContext({ type: 'episode', title: summary.episode_title });
        setIsChatOpen(true);
    };

    const handleOpenDetail = (summary: Summary) => {
        // Use episode title as ID for now (URL encoded)
        // Ideally we should use a real ID
        navigate(`/brief/${encodeURIComponent(summary.episode_title)}`);
    };

    // Filter Logic
    const filteredSummaries = summaries.filter(s => {
        const matchesTag = tagFilter
            ? s.key_topics.includes(tagFilter)
            : true;

        const matchesFeed = feedFilter
            ? s.podcast_name === feedFilter
            : true;

        const matchesSearch = searchQuery
            ? s.episode_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            s.podcast_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            s.summary.toLowerCase().includes(searchQuery.toLowerCase())
            : true;

        return matchesTag && matchesFeed && matchesSearch;
    });

    return (
        <div className="library-page">
            <header className="library-header pb-8 pt-4">
                <div className="flex justify-between items-end mb-6">
                    <div>
                        <h1 className="library-title">Smart Library</h1>
                        <p className="library-subtitle">
                            {filteredSummaries.length} insights collected
                        </p>
                    </div>
                </div>

                <div className="library-controls">
                    <div className="search-wrapper">
                        <Search className="search-icon" size={18} />
                        <input
                            type="text"
                            placeholder="Search concepts, speakers, or titles..."
                            className="search-input"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                    {tagFilter && (
                        <div className="filter-chip tag-chip">
                            <Filter size={14} />
                            <span>Tag: {tagFilter}</span>
                            <button onClick={() => navigate('/library')} className="clear-filter-btn">
                                <X size={14} />
                            </button>
                        </div>
                    )}
                    {feedFilter && (
                        <div className="filter-chip feed-chip">
                            <Radio size={14} />
                            <span>Feed: {feedFilter}</span>
                            <button onClick={() => navigate('/library')} className="clear-filter-btn">
                                <X size={14} />
                            </button>
                        </div>
                    )}
                </div>
            </header>

            {loading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-80 bg-slate-800/30 rounded-2xl"></div>
                    ))}
                </div>
            ) : (
                <div className="library-grid">
                    {filteredSummaries.map((summary, idx) => (
                        <SmartCard
                            key={idx}
                            summary={summary}
                            onChat={handleChat}
                            onOpen={handleOpenDetail}
                        />
                    ))}

                    {filteredSummaries.length === 0 && (
                        <div className="empty-state">
                            <p className="text-lg">No insights found matching your criteria.</p>
                        </div>
                    )}
                </div>
            )}

            {/* Local Chat Context for specific episode */}
            {isChatOpen && chatContext && (
                <ChatDrawer
                    isOpen={isChatOpen}
                    onClose={() => setIsChatOpen(false)}
                    initialContext={chatContext}
                />
            )}
        </div>
    );
}
