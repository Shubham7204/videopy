import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import VideoPlayer from './components/VideoPlayer';
import FaceTimeline from './components/FaceTimeline';

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
    processed_frames?: number;
    step_size?: number;
  };
}

const VideoAnalyzer: React.FC = () => {
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [faceData, setFaceData] = useState<FaceData | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [processing, setProcessing] = useState(false);

  const handleLoadVideo = async () => {
    setFaceData(null);
    setProcessing(false);
    setLoading(true);
    setError(null);
    setVideoUrl(null);

    try {
      const videoRes = await axios.get('http://localhost:5000/api/get_video');
      if (videoRes.data.error) throw new Error(videoRes.data.error);
      
      setVideoUrl(videoRes.data.video_url);
      setLoading(false);
      setProcessing(true);

      const processRes = await axios.post('http://localhost:5000/api/process_video');
      
      if (processRes.data.cached) {
        const faceRes = await axios.get('http://localhost:5000/api/face_data');
        if (faceRes.data?.face_detections) {
          setFaceData({
            face_detections: faceRes.data.face_detections,
            metadata: faceRes.data.metadata || { total_frames: 0, fps: 30 }
          });
          setProcessing(false);
          return;
        }
      }

      const pollInterval = setInterval(async () => {
        try {
          const faceRes = await axios.get('http://localhost:5000/api/face_data');
          if (faceRes.data?.face_detections) {
            setFaceData({
              face_detections: faceRes.data.face_detections,
              metadata: faceRes.data.metadata || { total_frames: 0, fps: 30 }
            });
            setProcessing(false);
            clearInterval(pollInterval);
          }
        } catch (err: any) {
          if (err.response?.status !== 404) {
            setError('Failed to load face detection data');
            setProcessing(false);
            clearInterval(pollInterval);
          }
        }
      }, 1000);

      setTimeout(() => {
        clearInterval(pollInterval);
        if (processing) {
          setError('Face detection timed out');
          setProcessing(false);
        }
      }, 30000);

    } catch (e: any) {
      setError(e.message || 'Failed to load video');
      setLoading(false);
      setProcessing(false);
    }
  };

  const handleTimeClick = (time: number) => {
    const video = document.querySelector('video');
    if (video) video.currentTime = time;
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">

        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <button
            onClick={handleLoadVideo}
            disabled={loading || processing}
            className={`w-full md:w-auto px-6 py-3 rounded-lg font-medium text-white transition-colors ${
              loading || processing 
                ? 'bg-gray-400 cursor-not-allowed' 
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {loading ? '⏳ Loading...' : processing ? '🔍 Analyzing...' : '🚀 Start Analysis'}
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
            {error.includes('not ready') && (
              <button onClick={handleLoadVideo} className="ml-2 underline">
                Try again
              </button>
            )}
          </div>
        )}

        {videoUrl && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <div className="bg-white rounded-lg shadow-md p-6">
                <h2 className="text-xl font-bold mb-4">📹 Video Stream</h2>
                <VideoPlayer
                  videoUrl={videoUrl}
                  faceData={faceData}
                  onTimeUpdate={setCurrentTime}
                />
              </div>
            </div>
            
            <div>
              <div className="bg-white rounded-lg shadow-md p-6">
                <h2 className="text-xl font-bold mb-4">👥 Detections</h2>
                {processing ? (
                  <div className="text-center py-8">
                    <div className="animate-pulse text-gray-400">Processing...</div>
                  </div>
                ) : (
                  <FaceTimeline
                    faceData={faceData}
                    currentTime={currentTime}
                    onTimeClick={handleTimeClick}
                  />
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <div className="min-h-screen">
        <nav className="bg-blue-600 text-white p-4">
          <h1 className="text-xl font-bold">CerebVision</h1>
        </nav>
        <Routes>
          <Route path="/" element={<VideoAnalyzer />} />
        </Routes>
      </div>
    </Router>
  );
};

export default App;