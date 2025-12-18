import { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { ChatDrawer } from './components/ChatDrawer';
import InboxPage from './pages/InboxPage';
import SmartLibraryPage from './pages/SmartLibraryPage';
import EpisodeExecBrief from './pages/EpisodeExecBrief';
import './App.css';

function App() {
    const [isChatOpen, setIsChatOpen] = useState(false);

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
                        <Route path="/" element={<Navigate to="/inbox" replace />} />
                        <Route path="/inbox" element={<InboxPage />} />
                        <Route path="/library" element={<SmartLibraryPage />} />
                        <Route path="/brief/:id" element={<EpisodeExecBrief />} />
                        <Route path="/favorites" element={<SmartLibraryPage />} />
                        <Route path="*" element={<div>Page Not Found</div>} />
                    </Routes>
                </div>
            </main>

            <ChatDrawer
                isOpen={isChatOpen}
                onClose={() => setIsChatOpen(false)}
            />
        </div>
    );
}

export default App;
