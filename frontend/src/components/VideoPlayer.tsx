import React, { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';

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
  videoUrl: string;
  faceData: FaceData | null;
  onTimeUpdate?: (time: number) => void;
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoUrl, faceData, onTimeUpdate }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [currentFaces, setCurrentFaces] = useState<FaceBox[]>([]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    let hls: Hls | null = null;

    if (Hls.isSupported()) {
      hls = new Hls();
      hls.loadSource(videoUrl);
      hls.attachMedia(video);
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = videoUrl;
    }

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
      hls?.destroy();
    };
  }, [videoUrl, faceData, onTimeUpdate]);

  return (
    <div className="relative">
      <div className="relative bg-black rounded-lg overflow-hidden" style={{ aspectRatio: '16/9' }}>
        <video
          ref={videoRef}
          className="w-full h-full object-contain"
          controls
          playsInline
        />
        
        {currentFaces.map((face, index) => (
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
      </div>
      
      {currentFaces.length > 0 && (
        <div className="mt-2 text-center">
          <span className="inline-block bg-green-100 text-green-800 text-sm px-2 py-1 rounded">
            {currentFaces.length} face{currentFaces.length !== 1 ? 's' : ''} detected
          </span>
        </div>
      )}
    </div>
  );
};

export default VideoPlayer;