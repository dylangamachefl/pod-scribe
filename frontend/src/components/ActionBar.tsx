import { RefreshCw, Bolt } from 'lucide-react';
import './ActionBar.css';

interface ActionBarProps {
    selectedCount: number;
    onSync: () => void;
    onTranscribe: () => void;
    isSyncing: boolean;
}

export function ActionBar({ selectedCount, onSync, onTranscribe, isSyncing }: ActionBarProps) {
    return (
        <div className="action-bar header-glass">
            <div className="actions-left">
                <h1 className="page-title">Inbox</h1>
            </div>

            <div className="actions-right">
                <button
                    className={`btn secondary ${isSyncing ? 'loading' : ''}`}
                    onClick={onSync}
                    disabled={isSyncing}
                >
                    <RefreshCw size={18} className={isSyncing ? 'spin' : ''} />
                    <span>{isSyncing ? 'Syncing...' : 'Sync Feeds'}</span>
                </button>

                <button
                    className="btn primary"
                    disabled={selectedCount === 0}
                    onClick={onTranscribe}
                >
                    <Bolt size={18} fill="currentColor" />
                    <span>
                        {selectedCount > 0
                            ? `Transcribe (${selectedCount})`
                            : 'Transcribe Selected'}
                    </span>
                </button>
            </div>
        </div>
    );
}
