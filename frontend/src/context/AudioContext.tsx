import React, { createContext, useContext, useState, useRef, useCallback } from 'react';

interface AudioContextType {
    currentAudioUrl: string | null;
    currentTime: number;
    duration: number;
    isPlaying: boolean;
    playAt: (url: string, timestamp: string) => void;
    seekTo: (timestamp: string) => void;
    togglePlay: () => void;
    // Internal refs/setters for AudioPlayer to sync back
    audioRef: React.RefObject<HTMLAudioElement>;
    setDuration: (d: number) => void;
    setCurrentTime: (t: number) => void;
    setIsPlaying: (p: boolean) => void;
}

const AudioContext = createContext<AudioContextType | undefined>(undefined);

export const useAudio = () => {
    const context = useContext(AudioContext);
    if (!context) {
        throw new Error('useAudio must be used within an AudioProvider');
    }
    return context;
};

export const AudioProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [currentAudioUrl, setCurrentAudioUrl] = useState<string | null>(null);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const audioRef = useRef<HTMLAudioElement>(null);

    const timestampToSeconds = (timestamp: string): number => {
        const parts = timestamp.split(':').map(Number);
        if (parts.length === 3) {
            return parts[0] * 3600 + parts[1] * 60 + parts[2];
        } else if (parts.length === 2) {
            return parts[0] * 60 + parts[1];
        }
        return 0;
    };

    const playAt = useCallback((url: string, timestamp: string) => {
        const seconds = timestampToSeconds(timestamp);

        if (currentAudioUrl !== url) {
            setCurrentAudioUrl(url);
            // We need to wait for the audio to load before seeking
            // The AudioPlayer component will handle the actual seek once metadata is loaded
            // But we set the target time here
            setCurrentTime(seconds);
        } else {
            if (audioRef.current) {
                audioRef.current.currentTime = seconds;
                audioRef.current.play();
                setIsPlaying(true);
            }
        }
    }, [currentAudioUrl]);

    const seekTo = useCallback((timestamp: string) => {
        const seconds = timestampToSeconds(timestamp);
        if (audioRef.current) {
            audioRef.current.currentTime = seconds;
        }
    }, []);

    const togglePlay = useCallback(() => {
        if (audioRef.current) {
            if (isPlaying) {
                audioRef.current.pause();
            } else {
                audioRef.current.play();
            }
            setIsPlaying(!isPlaying);
        }
    }, [isPlaying]);

    const value = {
        currentAudioUrl,
        currentTime,
        duration,
        isPlaying,
        playAt,
        seekTo,
        togglePlay,
        audioRef,
        setDuration,
        setCurrentTime,
        setIsPlaying
    };

    return (
        <AudioContext.Provider value={value}>
            {children}
        </AudioContext.Provider>
    );
};
