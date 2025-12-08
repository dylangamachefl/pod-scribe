import { useState } from 'react'
import './App.css'
import DashboardPage from './pages/DashboardPage'
import FeedManagerPage from './pages/FeedManagerPage'
import EpisodeQueuePage from './pages/EpisodeQueuePage'
import LibraryPage from './pages/LibraryPage'

type PageType = 'dashboard' | 'queue' | 'feeds' | 'library';

function App() {
    const [currentPage, setCurrentPage] = useState<PageType>('dashboard')
    const [isTransitioning, setIsTransitioning] = useState(false)

    const changePage = (newPage: PageType) => {
        if (newPage === currentPage) return

        setIsTransitioning(true)
        setTimeout(() => {
            setCurrentPage(newPage)
            window.scrollTo({ top: 0, behavior: 'smooth' })
            setIsTransitioning(false)
        }, 150)
    }

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
                            onClick={() => changePage('dashboard')}
                            title="Dashboard"
                            aria-label="Navigate to Dashboard"
                            aria-current={currentPage === 'dashboard' ? 'page' : undefined}
                        >
                            📊 Dashboard
                        </button>
                        <button
                            className={`nav-tab ${currentPage === 'queue' ? 'active' : ''}`}
                            onClick={() => changePage('queue')}
                            title="Episode Queue"
                            aria-label="Navigate to Episode Queue"
                            aria-current={currentPage === 'queue' ? 'page' : undefined}
                        >
                            📥 Queue
                        </button>
                        <button
                            className={`nav-tab ${currentPage === 'feeds' ? 'active' : ''}`}
                            onClick={() => changePage('feeds')}
                            title="Feed Manager"
                            aria-label="Navigate to Feed Manager"
                            aria-current={currentPage === 'feeds' ? 'page' : undefined}
                        >
                            📡 Feeds
                        </button>
                        <button
                            className={`nav-tab ${currentPage === 'library' ? 'active' : ''}`}
                            onClick={() => changePage('library')}
                            title="Library"
                            aria-label="Navigate to Library"
                            aria-current={currentPage === 'library' ? 'page' : undefined}
                        >
                            📚 Library
                        </button>
                    </div>
                </div>
            </nav>

            <main className={`main-content ${isTransitioning ? 'transitioning' : ''}`}>
                {renderPage()}
            </main>
        </div>
    )
}

export default App

