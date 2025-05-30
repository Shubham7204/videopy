import React from 'react';

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

interface FaceTimelineProps {
  faceData: FaceData | null;
  currentTime: number;
  onTimeClick: (time: number) => void;
}

const FaceTimeline: React.FC<FaceTimelineProps> = ({ faceData, currentTime, onTimeClick }) => {
  if (!faceData?.face_detections?.length) {
    return (
      <div className="text-center py-8 text-gray-500">
        <div className="text-3xl mb-2">🔍</div>
        <p>No detections yet</p>
      </div>
    );
  }

  const formatTime = (timestamp: string) => {
    const time = parseFloat(timestamp);
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-3 max-h-96 overflow-y-auto">
      <div className="text-sm text-gray-600 mb-3">
        {faceData.face_detections.length} detections found
      </div>
      
      {faceData.face_detections.map((detection) => {
        const detectionTime = detection.frame / faceData.metadata.fps;
        const isActive = Math.abs(currentTime - detectionTime) < 1;
        
        return (
          <div
            key={`${detection.frame}-${detection.timestamp}`}
            className={`p-3 rounded-lg cursor-pointer transition-colors border ${
              isActive 
                ? 'bg-blue-50 border-blue-300' 
                : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
            }`}
            onClick={() => onTimeClick(detectionTime)}
          >
            <div className="flex justify-between items-center">
              <span className="font-medium text-sm">
                {formatTime(detection.timestamp)}
              </span>
              <span className="text-xs text-gray-500">
                Frame {detection.frame}
              </span>
            </div>
            
            <div className="flex items-center mt-1">
              <span className="text-lg mr-2">
                {detection.faces.length === 1 ? '👤' : '👥'}
              </span>
              <span className="text-sm text-gray-700">
                {detection.faces.length} face{detection.faces.length !== 1 ? 's' : ''}
              </span>
              {isActive && (
                <span className="ml-2 w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default FaceTimeline;