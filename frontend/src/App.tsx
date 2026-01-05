import { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { ChatDrawer } from './components/ChatDrawer';
import InboxPage from './pages/InboxPage';
import SmartLibraryPage from './pages/SmartLibraryPage';
import EpisodeExecBrief from './pages/EpisodeExecBrief';
import DashboardPage from './pages/DashboardPage';
import FeedManagerPage from './pages/FeedManagerPage';
import './App.css';

function App() {
    const [isChatOpen, setIsChatOpen] = useState(false);
    const [chatContext, setChatContext] = useState<any>(null);

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
                        {/* Global Search could go here */}
                    </div>
                    <button className="chat-trigger-btn" onClick={() => setIsChatOpen(true)}>
                        <span>Ask AI Assistant</span>
                        <span className="kbd-shortcut">⌘K</span>
                    </button>
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
