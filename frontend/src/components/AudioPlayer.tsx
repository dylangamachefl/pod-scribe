import { useEffect, useState } from 'react';
import './AudioPlayer.css';
import { useAudio } from '../context/AudioContext';

interface AudioPlayerProps {
    audioUrl: string;
}

function AudioPlayer({ audioUrl }: AudioPlayerProps) {
    const {
        audioRef,
        isPlaying,
        currentTime,
        duration,
        togglePlay,
        setDuration,
        setCurrentTime,
        setIsPlaying,
        currentAudioUrl
    } = useAudio();

    const [volume, setVolume] = useState(1);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [isLoading, setIsLoading] = useState(false);

    // Sync with global audio URL if provided as prop
    // This allows the detail modal to tell the player what to load initially
    useEffect(() => {
        if (audioUrl && currentAudioUrl !== audioUrl) {
            // If the prop changes and doesn't match context, we might want to load it
            // However, the context is the source of truth for what's actually playing
        }
    }, [audioUrl, currentAudioUrl]);

    useEffect(() => {
        const audio = audioRef.current;
        if (!audio) return;

        const handleLoadStart = () => setIsLoading(true);
        const handleCanPlay = () => setIsLoading(false);
        const handleLoadedMetadata = () => {
            setDuration(audio.duration);
            setIsLoading(false);
            // If we have a pending seek time from playAt, apply it
            if (currentTime > 0) {
                audio.currentTime = currentTime;
            }
        };
        const handleTimeUpdate = () => setCurrentTime(audio.currentTime);
        const handlePlay = () => setIsPlaying(true);
        const handlePause = () => setIsPlaying(false);
        const handleEnded = () => setIsPlaying(false);

        audio.addEventListener('loadstart', handleLoadStart);
        audio.addEventListener('canplay', handleCanPlay);
        audio.addEventListener('loadedmetadata', handleLoadedMetadata);
        audio.addEventListener('timeupdate', handleTimeUpdate);
        audio.addEventListener('play', handlePlay);
        audio.addEventListener('pause', handlePause);
        audio.addEventListener('ended', handleEnded);

        return () => {
            audio.removeEventListener('loadstart', handleLoadStart);
            audio.removeEventListener('canplay', handleCanPlay);
            audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
            audio.removeEventListener('timeupdate', handleTimeUpdate);
            audio.removeEventListener('play', handlePlay);
            audio.removeEventListener('pause', handlePause);
            audio.removeEventListener('ended', handleEnded);
        };
    }, [audioRef, setDuration, setCurrentTime, setIsPlaying, currentTime]);

    const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newTime = parseFloat(e.target.value);
        if (audioRef.current) {
            audioRef.current.currentTime = newTime;
            setCurrentTime(newTime);
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

    // If there is no audio URL in context and none provided, show nothing or placeholder
    if (!currentAudioUrl && !audioUrl) return null;

    return (
        <div className="audio-player glass">
            <audio
                ref={audioRef}
                src={currentAudioUrl || audioUrl}
                preload="metadata"
            />

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
