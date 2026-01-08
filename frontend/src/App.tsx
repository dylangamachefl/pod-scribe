import { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { ChatDrawer } from './components/ChatDrawer';
import InboxPage from './pages/InboxPage';
import SmartLibraryPage from './pages/SmartLibraryPage';
import EpisodeExecBrief from './pages/EpisodeExecBrief';
import DashboardPage from './pages/DashboardPage';
import FeedManagerPage from './pages/FeedManagerPage';
import { transcriptionApi } from './api';
import './App.css';
import { Activity } from 'lucide-react';

function App() {
    const [isChatOpen, setIsChatOpen] = useState(false);
    const [chatContext, setChatContext] = useState<any>(null);
    const [isProcessing, setIsProcessing] = useState(false);

    useEffect(() => {
        const checkStatus = async () => {
            try {
                const status = await transcriptionApi.getTranscriptionStatus();
                setIsProcessing(status.is_running);
            } catch (error) {
                console.error('Failed to get status in App:', error);
            }
        };
        checkStatus();
        const interval = setInterval(checkStatus, 10000);
        return () => clearInterval(interval);
    }, []);

    // Expose toggle to window for simple cross-component triggering
    useEffect(() => {
        (window as any).toggleGlobalChat = (context?: any) => {
            if (context) setChatContext(context);
            else setChatContext(null);
            setIsChatOpen(true);
        };
        return () => { delete (window as any).toggleGlobalChat; };
    }, []);

    return (
        <div className="app-container">
            <Sidebar />

            <main className="main-content">
                <header className="top-header glass">
                    <div className="header-search">
                        {isProcessing && (
                            <div className="header-processing-indicator">
                                <Activity size={16} className="spin text-accent" />
                                <span>Processing Pipeline</span>
                            </div>
                        )}
                    </div>
                </header>

                <div className="content-scroll-area">
                    <Routes>
                        <Route path="/" element={<Navigate to="/dashboard" replace />} />
                        <Route path="/dashboard" element={<DashboardPage />} />
                        <Route path="/inbox" element={<InboxPage />} />
                        <Route path="/library" element={<SmartLibraryPage />} />
                        <Route path="/brief/:id" element={<EpisodeExecBrief />} />
                        <Route path="/favorites" element={<SmartLibraryPage />} />
                        <Route path="/feeds" element={<FeedManagerPage />} />
                        <Route path="*" element={<div>Page Not Found</div>} />
                    </Routes>
                </div>
            </main>

            <ChatDrawer
                isOpen={isChatOpen}
                onClose={() => setIsChatOpen(false)}
                initialContext={chatContext}
            />
        </div>
    );
}

export default App;
