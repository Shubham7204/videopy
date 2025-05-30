import cv2
import json
import os
import time
import logging
import threading
from datetime import timedelta

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
VIDEO_FILENAME = 'office.mp4'

# Create directories if they don't exist
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

class FaceDetector:
    _instance = None
    _processing = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FaceDetector, cls).__new__(cls)
            cls._instance.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        return cls._instance
    
    @property
    def is_processing(self):
        return self._processing
    
    def should_process_video(self, video_path, output_path):
        """Check if we need to process the video by comparing modification times"""
        if not os.path.exists(output_path):
            return True
            
        if not os.path.exists(video_path):
            return False
            
        video_mtime = os.path.getmtime(video_path)
        data_mtime = os.path.getmtime(output_path)
        
        # If video is newer than face data, we should reprocess
        return video_mtime > data_mtime

    def process_video(self, video_path, output_path):
        if self._processing:
            logger.warning("Already processing a video")
            return False
            
        self._processing = True
        logger.info(f"Starting face detection for video: {video_path}")
        """Process video and save face detection data"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                self._processing = False
                return False
                
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            logger.info(f"Video loaded: {frame_count} frames at {fps} FPS")
        
            face_data = []
            current_frame = 0
            
            # Process every Nth frame (e.g., every 15th frame)
            frame_step = 15
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Only process every Nth frame
                if current_frame % frame_step == 0:
                    # Log progress
                    if current_frame % (frame_step * 10) == 0:
                        progress = (current_frame / frame_count) * 100
                        logger.info(f"Processing: {progress:.1f}% complete")
                    
                    # Calculate timestamp
                    timestamp = str(timedelta(seconds=current_frame/fps))
                    
                    # Resize frame for faster processing
                    height = frame.shape[0]
                    width = frame.shape[1]
                    scale_factor = 0.5  # Process at half resolution
                    small_frame = cv2.resize(frame, (int(width * scale_factor), int(height * scale_factor)))
                    
                    # Detect faces
                    gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
                    faces = self.face_cascade.detectMultiScale(
                        gray,
                        scaleFactor=1.2,  # Increased for faster detection
                        minNeighbors=4,   # Reduced for faster detection
                        minSize=(20, 20)  # Minimum face size
                    )
                    
                    # Scale back the coordinates to original size
                    faces = [(int(x/scale_factor), int(y/scale_factor), 
                             int(w/scale_factor), int(h/scale_factor)) for x, y, w, h in faces]
                    
                    # Save face data if any faces detected
                    if len(faces) > 0:
                        frame_data = {
                            "frame": current_frame,
                            "timestamp": timestamp,
                            "faces": [{"x": int(x), "y": int(y), "width": int(w), "height": int(h)} 
                                     for (x, y, w, h) in faces]
                        }
                        face_data.append(frame_data)
                
                current_frame += 1
        
            cap.release()
            
            # Save face data to file
            with open(output_path, 'w') as f:
                json.dump({
                    "face_detections": face_data,
                    "metadata": {
                        "total_frames": frame_count,
                        "fps": fps,
                        "processed_frames": current_frame,
                        "step_size": frame_step
                    }
                }, f, indent=2)
            
            logger.info(f"Face detection completed. Data saved to {output_path}")
            self._processing = False
            return True
            
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            self._processing = False
            return False

def process_video_background():
    """Process video in background thread"""
    time.sleep(2)  # Wait for server to stabilize
    
    video_path = os.path.join(UPLOADS_DIR, VIDEO_FILENAME)
    output_path = os.path.join(DATA_DIR, 'face_data.json')
    
    if should_process_video(video_path, output_path):
        logger.info("Processing video: new video or no existing face data")
        detector = FaceDetector()
        detector.process_video(video_path, output_path)
    else:
        logger.info("Using existing face data: video hasn't changed")

if __name__ == '__main__':
    logger.info("Starting face detection service")
    thread = threading.Thread(target=process_video_background, daemon=True)
    thread.start()
    
    # Keep the script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down face detection service")