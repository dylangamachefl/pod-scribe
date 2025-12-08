import { useRef, useState, useEffect } from 'react';
import './AudioPlayer.css';

interface AudioPlayerProps {
    audioUrl: string;
}

function AudioPlayer({ audioUrl }: AudioPlayerProps) {
    const audioRef = useRef<HTMLAudioElement>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [volume, setVolume] = useState(1);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        const audio = audioRef.current;
        if (!audio) return;

        const handleLoadStart = () => setIsLoading(true);
        const handleCanPlay = () => setIsLoading(false);
        const handleLoadedMetadata = () => {
            setDuration(audio.duration);
            setIsLoading(false);
        };
        const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
        const handleEnded = () => setIsPlaying(false);

        audio.addEventListener('loadstart', handleLoadStart);
        audio.addEventListener('canplay', handleCanPlay);
        audio.addEventListener('loadedmetadata', handleLoadedMetadata);
        audio.addEventListener('timeupdate', handleTimeUpdate);
        audio.addEventListener('ended', handleEnded);

        return () => {
            audio.removeEventListener('loadstart', handleLoadStart);
            audio.removeEventListener('canplay', handleCanPlay);
            audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
            audio.removeEventListener('timeupdate', handleTimeUpdate);
            audio.removeEventListener('ended', handleEnded);
        };
    }, []);

    const togglePlay = () => {
        if (audioRef.current) {
            if (isPlaying) {
                audioRef.current.pause();
            } else {
                audioRef.current.play();
            }
            setIsPlaying(!isPlaying);
        }
    };

    const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newTime = parseFloat(e.target.value);
        setCurrentTime(newTime);
        if (audioRef.current) {
            audioRef.current.currentTime = newTime;
        }
    };

    const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newVolume = parseFloat(e.target.value);
        setVolume(newVolume);
        if (audioRef.current) {
            audioRef.current.volume = newVolume;
        }
    };

    const handlePlaybackRateChange = (rate: number) => {
        setPlaybackRate(rate);
        if (audioRef.current) {
            audioRef.current.playbackRate = rate;
        }
    };

    const formatTime = (seconds: number) => {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    return (
        <div className="audio-player glass">
            <audio ref={audioRef} src={audioUrl} preload="metadata" />

            <div className="player-main">
                <button
                    className="play-button"
                    onClick={togglePlay}
                    disabled={isLoading}
                    aria-label={isPlaying ? 'Pause' : 'Play'}
                >
                    {isLoading ? '⏳' : isPlaying ? '⏸' : '▶'}
                </button>

                <div className="progress-section">
                    <div className="time-display">
                        <span className="current-time">{formatTime(currentTime)}</span>
                        <span className="separator">/</span>
                        <span className="total-time">{formatTime(duration)}</span>
                    </div>

                    <input
                        type="range"
                        className="progress-bar"
                        min="0"
                        max={duration || 0}
                        value={currentTime}
                        onChange={handleSeek}
                        disabled={isLoading}
                        aria-label="Seek audio"
                    />
                </div>
            </div>

            <div className="player-controls">
                <div className="playback-speed">
                    <label>Speed:</label>
                    <div className="speed-buttons">
                        {[0.5, 0.75, 1, 1.25, 1.5, 2].map(rate => (
                            <button
                                key={rate}
                                className={`speed-btn ${playbackRate === rate ? 'active' : ''}`}
                                onClick={() => handlePlaybackRateChange(rate)}
                                aria-label={`Playback speed ${rate}x`}
                            >
                                {rate}x
                            </button>
                        ))}
                    </div>
                </div>

                <div className="volume-control">
                    <label>🔊</label>
                    <input
                        type="range"
                        className="volume-slider"
                        min="0"
                        max="1"
                        step="0.1"
                        value={volume}
                        onChange={handleVolumeChange}
                        aria-label="Volume control"
                    />
                </div>
            </div>
        </div>
    );
}

export default AudioPlayer;
