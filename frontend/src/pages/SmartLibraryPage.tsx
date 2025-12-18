import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { summarizationApi } from '../api';
import { Summary } from '../api/types';
import { SmartCard } from '../components/SmartCard';
import { ChatDrawer } from '../components/ChatDrawer';
import { Search, Filter } from 'lucide-react';

export default function SmartLibraryPage() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const tagFilter = searchParams.get('tag');

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

        const matchesSearch = searchQuery
            ? s.episode_title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            s.podcast_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            s.summary.toLowerCase().includes(searchQuery.toLowerCase())
            : true;

        return matchesTag && matchesSearch;
    });

    return (
        <div className="library-page">
            <header className="library-header pb-8 pt-4">
                <div className="flex justify-between items-end mb-6">
                    <div>
                        <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-teal-200 to-teal-500">
                            Smart Library
                        </h1>
                        <p className="text-slate-400 mt-2">
                            {filteredSummaries.length} insights collected
                        </p>
                    </div>
                </div>

                <div className="search-bar-wrapper flex gap-4">
                    <div className="relative flex-1">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" size={20} />
                        <input
                            type="text"
                            placeholder="Search concepts, speakers, or titles..."
                            className="w-full bg-slate-800/50 border border-slate-700/50 rounded-xl py-3 pl-12 pr-4 text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500/50 transition-all"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>
                    {tagFilter && (
                        <div className="flex items-center gap-2 px-4 py-2 bg-teal-500/10 border border-teal-500/20 rounded-xl text-teal-300">
                            <Filter size={16} />
                            <span>Filter: #{tagFilter}</span>
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
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pb-12">
                    {filteredSummaries.map((summary, idx) => (
                        <SmartCard
                            key={idx}
                            summary={summary}
                            onChat={handleChat}
                            onOpen={handleOpenDetail}
                        />
                    ))}

                    {filteredSummaries.length === 0 && (
                        <div className="col-span-full text-center py-20 text-slate-500">
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
