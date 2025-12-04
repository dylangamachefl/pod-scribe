import { useState } from 'react'
import './App.css'
import DashboardPage from './pages/DashboardPage'
import FeedManagerPage from './pages/FeedManagerPage'
import EpisodeQueuePage from './pages/EpisodeQueuePage'
import LibraryPage from './pages/LibraryPage'

type PageType = 'dashboard' | 'queue' | 'feeds' | 'library';

function App() {
    const [currentPage, setCurrentPage] = useState<PageType>('dashboard')

    const renderPage = () => {
        switch (currentPage) {
            case 'dashboard':
                return <DashboardPage />;
            case 'queue':
                return <EpisodeQueuePage />;
            case 'feeds':
                return <FeedManagerPage />;
            case 'library':
                return <LibraryPage />;
            default:
                return <DashboardPage />;
        }
    };

    return (
        <div className="app">
            <nav className="navbar glass">
                <div className="navbar-content">
                    <h1 className="logo">
                        <span className="logo-icon">🎙️</span>
                        Podcast Manager
                    </h1>

                    <div className="nav-tabs">
                        <button
                            className={`nav-tab ${currentPage === 'dashboard' ? 'active' : ''}`}
                            onClick={() => setCurrentPage('dashboard')}
                            title="Dashboard"
                        >
                            📊 Dashboard
                        </button>
                        <button
                            className={`nav-tab ${currentPage === 'queue' ? 'active' : ''}`}
                            onClick={() => setCurrentPage('queue')}
                            title="Episode Queue"
                        >
                            📥 Queue
                        </button>
                        <button
                            className={`nav-tab ${currentPage === 'feeds' ? 'active' : ''}`}
                            onClick={() => setCurrentPage('feeds')}
                            title="Feed Manager"
                        >
                            📡 Feeds
                        </button>
                        <button
                            className={`nav-tab ${currentPage === 'library' ? 'active' : ''}`}
                            onClick={() => setCurrentPage('library')}
                            title="Library"
                        >
                            📚 Library
                        </button>
                    </div>
                </div>
            </nav>

            <main className="main-content">
                {renderPage()}
            </main>
        </div>
    )
}

export default App

