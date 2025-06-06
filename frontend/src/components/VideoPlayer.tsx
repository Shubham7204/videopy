import React, { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';
import axios from 'axios';

interface FaceBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface FaceDetection {
  frame: number;
  timestamp: string;
  faces: FaceBox[];
}

interface FaceData {
  face_detections: FaceDetection[];
  metadata: {
    total_frames: number;
    fps: number;
  };
}

interface VideoPlayerProps {
  mode: 'simple' | 'analysis';
  videoUrl?: string;
  faceData?: FaceData | null;
  onTimeUpdate?: (time: number) => void;
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({ mode, videoUrl: propVideoUrl, faceData, onTimeUpdate }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const [currentFaces, setCurrentFaces] = useState<FaceBox[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(propVideoUrl || null);
  const [isLive, setIsLive] = useState(true);
  const [showGoLive, setShowGoLive] = useState(false);

  useEffect(() => {
    // Cleanup function for HLS instance
    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (propVideoUrl) {
      setVideoUrl(propVideoUrl);
    }
  }, [propVideoUrl]);

  const checkIfLive = () => {
    const video = videoRef.current;
    const hls = hlsRef.current;
    
    if (!video || !hls || mode !== 'simple') return;

    try {
      const levels = hls.levels;
      if (levels && levels.length > 0) {
        const currentLevel = levels[hls.currentLevel] || levels[0];
        if (currentLevel && currentLevel.details) {
          const fragments = currentLevel.details.fragments;
          if (fragments && fragments.length > 0) {
            const lastFragment = fragments[fragments.length - 1];
            const liveEdge = lastFragment.start + lastFragment.duration;
            const currentTime = video.currentTime;
            const timeDiff = liveEdge - currentTime;
            
            // Consider "live" if within 10 seconds of the live edge
            const isCurrentlyLive = timeDiff <= 10;
            setIsLive(isCurrentlyLive);
            setShowGoLive(!isCurrentlyLive && timeDiff > 10);
          }
        }
      }
    } catch (error) {
      console.warn('Error checking live status:', error);
    }
  };

  const goToLive = () => {
    const video = videoRef.current;
    const hls = hlsRef.current;
    
    if (!video || !hls) return;

    try {
      // Get the live edge position
      const levels = hls.levels;
      if (levels && levels.length > 0) {
        const currentLevel = levels[hls.currentLevel] || levels[0];
        if (currentLevel && currentLevel.details) {
          const fragments = currentLevel.details.fragments;
          if (fragments && fragments.length > 0) {
            const lastFragment = fragments[fragments.length - 1];
            const livePosition = lastFragment.start + lastFragment.duration - 5; // 5 seconds from live edge
            video.currentTime = Math.max(0, livePosition);
            setIsLive(true);
            setShowGoLive(false);
          }
        }
      }
    } catch (error) {
      console.error('Error going to live position:', error);
      // Fallback: jump to the end of the buffer
      if (video.buffered.length > 0) {
        video.currentTime = video.buffered.end(video.buffered.length - 1) - 2;
      }
    }
  };

  const setupVideo = (url: string) => {
    const video = videoRef.current;
    if (!video) {
      console.error('Video element not found');
      return false;
    }

    // Cleanup previous HLS instance if it exists
    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }

    try {
    if (Hls.isSupported()) {
        const hls = new Hls({
          enableWorker: true,
          lowLatencyMode: true,
          backBufferLength: 30,
          liveBackBufferLength: 30,
          liveSyncDurationCount: 3,
          liveMaxLatencyDurationCount: 10
        });
        
        hls.on(Hls.Events.ERROR, (_, data) => {
          if (data.fatal) {
            setError('Video playback error. Please try again.');
            hls.destroy();
          }
        });

        hls.on(Hls.Events.MANIFEST_LOADED, () => {
          if (mode === 'simple') {
            checkIfLive();
          }
        });

        hls.on(Hls.Events.FRAG_LOADED, () => {
          if (mode === 'simple') {
            checkIfLive();
          }
        });

        hls.loadSource(url);
      hls.attachMedia(video);
        hlsRef.current = hls;

        // Add time update listener for live checking
        if (mode === 'simple') {
          video.addEventListener('timeupdate', checkIfLive);
        }
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = url;
      } else {
        setError('HLS is not supported in your browser');
        return false;
      }

      if (mode === 'simple') {
        video.play().catch(e => {
          console.warn('Auto-play failed:', e);
        });
      }
      
      return true;
    } catch (error) {
      console.error('Error setting up video:', error);
      setError('Failed to setup video player');
      return false;
    }
  };

  const handleStartStream = async () => {
    if (loading) return;
    
    setLoading(true);
    setError(null);

    try {
      const res = await axios.get('http://localhost:5000/api/start_stream');
      if (res.data.error) {
        throw new Error(res.data.error);
      }

      const newVideoUrl = res.data.video_url;
      setVideoUrl(newVideoUrl);
      
      // Ensure video element is available before setting up
      const checkVideoAndSetup = () => {
        const video = videoRef.current;
        if (video) {
          setupVideo(newVideoUrl);
        } else {
          // Retry after a short delay if video element is not ready
          setTimeout(checkVideoAndSetup, 50);
        }
      };
      
      checkVideoAndSetup();

    } catch (e: any) {
      console.error('Error:', e);
      setError(e.message || 'Failed to start video stream');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!videoUrl) return;

    // Setup video when videoUrl changes (for analysis mode)
    if (mode === 'analysis') {
      setupVideo(videoUrl);
    }

    const video = videoRef.current;
    if (!video || mode !== 'analysis') return;

    const updateFaces = () => {
      if (!faceData?.face_detections || !video) return;
      
      const fps = faceData.metadata.fps || 30;
      const frameNumber = Math.floor(video.currentTime * fps);
      const detection = faceData.face_detections.find(d => Math.abs(d.frame - frameNumber) <= 1);
      
      setCurrentFaces(detection?.faces || []);
      onTimeUpdate?.(video.currentTime);
    };

    video.addEventListener('timeupdate', updateFaces);
    video.addEventListener('loadedmetadata', updateFaces);

    return () => {
      video.removeEventListener('timeupdate', updateFaces);
      video.removeEventListener('loadedmetadata', updateFaces);
    };
  }, [videoUrl, faceData, onTimeUpdate, mode]);

  const renderVideo = () => (
    <div className="mt-6 w-full max-w-4xl">
      <div className="relative bg-black rounded-lg overflow-hidden" style={{ aspectRatio: '16/9' }}>
        <video
          ref={videoRef}
          className="w-full h-full object-contain"
          controls
          playsInline
        />
        
        {mode === 'analysis' && currentFaces.map((face, index) => (
          <div
            key={`${index}-${face.x}-${face.y}`}
            className="absolute border-2 border-green-400 pointer-events-none"
            style={{
              left: `${(face.x / 640) * 100}%`,
              top: `${(face.y / 360) * 100}%`,
              width: `${(face.width / 640) * 100}%`,
              height: `${(face.height / 360) * 100}%`,
            }}
          >
            <span className="absolute -top-6 left-0 bg-green-400 text-white text-xs px-1 rounded">
              Face {index + 1}
            </span>
          </div>
        ))}

        {/* Go Live Button - positioned like Hotstar */}
        {mode === 'simple' && showGoLive && (
          <div className="absolute bottom-4 right-4">
            <button
              onClick={goToLive}
              className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-full flex items-center space-x-2 shadow-lg transition-all duration-200 transform hover:scale-105"
            >
              <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
              <span className="text-sm font-medium">GO LIVE</span>
            </button>
          </div>
        )}

        {/* Live Indicator */}
        {mode === 'simple' && isLive && videoUrl && (
          <div className="absolute top-4 left-4">
            <div className="bg-red-600 text-white px-3 py-1 rounded-full flex items-center space-x-2">
              <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
              <span className="text-xs font-medium">LIVE</span>
            </div>
          </div>
        )}
      </div>
      
      {mode === 'analysis' && currentFaces.length > 0 && (
        <div className="mt-2 text-center">
          <span className="inline-block bg-green-100 text-green-800 text-sm px-2 py-1 rounded">
            {currentFaces.length} face{currentFaces.length !== 1 ? 's' : ''} detected
          </span>
        </div>
      )}
    </div>
  );

  const renderSimpleMode = () => (
    <div className="flex flex-col items-center justify-center min-h-screen p-6 bg-gray-100">
      <button
        onClick={handleStartStream}
        disabled={loading}
        className={`px-6 py-3 rounded-lg font-medium text-white transition-colors ${
          loading ? 'bg-gray-500 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
        }`}
      >
        {loading ? '⏳ Loading...' : '▶️ Start Stream'}
      </button>

      {error && (
        <div className="mt-4 text-red-500 bg-red-50 px-4 py-2 rounded-lg">
          {error}
          <button
            onClick={handleStartStream}
            className="ml-2 underline text-blue-500"
          >
            Try again
          </button>
        </div>
      )}

      {renderVideo()}
    </div>
  );

  const renderAnalysisMode = () => (
    <div className="relative">
      {renderVideo()}
    </div>
  );

  return mode === 'simple' ? renderSimpleMode() : renderAnalysisMode();
};

export default VideoPlayer;