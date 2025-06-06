from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import os
import subprocess
import threading
import logging
import time
import json
from face_detector import FaceDetector

app = Flask(__name__)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
STREAMS_DIR = os.path.join(os.path.dirname(__file__), 'streams')
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
VIDEO_FILENAME = 'office.mp4'  # Updated to match your video file

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STREAMS_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize face detector
face_detector = FaceDetector()

def convert_to_hls():
    video_path = os.path.join(UPLOADS_DIR, VIDEO_FILENAME)
    stream_output_dir = os.path.join(STREAMS_DIR, 'sample')
    os.makedirs(stream_output_dir, exist_ok=True)

    m3u8_path = os.path.join(stream_output_dir, 'playlist.m3u8')

    # Log paths for debugging
    logger.debug(f"Video path: {video_path}")
    logger.debug(f"Stream output dir: {stream_output_dir}")
    logger.debug(f"M3U8 path: {m3u8_path}")

    # Clear old segments
    for file in os.listdir(stream_output_dir):
        os.remove(os.path.join(stream_output_dir, file))

    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return None

    # Simple, proven FFmpeg settings with better quality
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', video_path,
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-b:v', '1200k',           # Increased from 800k for better quality
        '-b:a', '192k',            # Increased from 128k for better audio
        '-f', 'hls',
        '-hls_time', '6',          # Keep 6-second segments as before
        '-hls_list_size', '0',
        '-hls_segment_filename', os.path.join(stream_output_dir, 'segment_%03d.ts'),
        m3u8_path
    ]

    logger.debug(f"Starting FFmpeg: {' '.join(ffmpeg_cmd)}")
    try:
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        def log_ffmpeg_output(proc):
            while proc.poll() is None:
                line = proc.stderr.readline()
                if line:
                    logger.debug(f"FFmpeg: {line.strip()}")
            _, stderr = proc.communicate()
            if proc.returncode != 0:
                logger.error(f"FFmpeg failed with code {proc.returncode}: {stderr}")
            else:
                logger.info("FFmpeg completed successfully")

        threading.Thread(target=log_ffmpeg_output, args=(process,), daemon=True).start()

        # Wait for playlist creation
        for _ in range(60):
            if os.path.exists(m3u8_path) and os.path.getsize(m3u8_path) > 0:
                logger.info(f"Playlist created: {m3u8_path}")
                return '/streams/sample/playlist.m3u8'
            time.sleep(1)
        logger.error("Timeout waiting for playlist creation")
        return None
    except Exception as e:
        logger.error(f"FFmpeg setup failed: {str(e)}")
        return None

def start_hls_conversion():
    time.sleep(2)  # Wait for Flask to stabilize
    logger.info("Initiating HLS conversion")
    try:
        result = convert_to_hls()
        if not result:
            logger.error("Failed to start HLS conversion")
        else:
            logger.info(f"HLS conversion successful: {result}")
    except Exception as e:
        logger.error(f"HLS conversion thread failed: {str(e)}")

@app.route('/api/video_status', methods=['GET'])
def video_status():
    """Check if video file exists and get info"""
    video_path = os.path.join(UPLOADS_DIR, VIDEO_FILENAME)
    
    if not os.path.exists(video_path):
        return jsonify({
            "status": "error",
            "message": f"Video file '{VIDEO_FILENAME}' not found in uploads directory",
            "video_path": video_path,
            "uploads_dir_contents": os.listdir(UPLOADS_DIR) if os.path.exists(UPLOADS_DIR) else []
        }), 404
    
    file_size = os.path.getsize(video_path)
    return jsonify({
        "status": "success",
        "video_file": VIDEO_FILENAME,
        "video_path": video_path,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "uploads_dir_contents": os.listdir(UPLOADS_DIR)
    })

@app.route('/api/start_stream', methods=['GET'])
def start_stream():
    """Start high quality video streaming"""
    try:
        result = convert_to_hls()
        if result:
            return jsonify({
                "status": "success",
                "video_url": f"http://localhost:5000{result}"
            })
        return jsonify({"status": "error", "message": "Failed to start stream"}), 500
    except Exception as e:
        logger.error(f"Error starting stream: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/get_video', methods=['GET'])
def get_video():
    hls_path = '/streams/sample/playlist.m3u8'
    m3u8_full_path = os.path.join(STREAMS_DIR, 'sample', 'playlist.m3u8')
    if os.path.exists(m3u8_full_path) and os.path.getsize(m3u8_full_path) > 0:
        return jsonify({"video_url": f"http://localhost:5000{hls_path}"})
    else:
        logger.warning("HLS stream not ready")
        return jsonify({"error": "HLS stream not ready yet, please try again in a moment"}), 503

@app.route('/streams/sample/<path:filename>')
def serve_stream(filename):
    logger.debug(f"Serving file: {filename}")
    try:
        return send_from_directory(os.path.join(STREAMS_DIR, 'sample'), filename)
    except Exception as e:
        logger.error(f"Error serving file {filename}: {str(e)}")
        return jsonify({"error": "File not found"}), 404

@app.route('/api/process_video', methods=['POST'])
def process_video():
    """Process video for face detection separately from streaming"""
    video_path = os.path.join(UPLOADS_DIR, VIDEO_FILENAME)
    output_path = os.path.join(DATA_DIR, 'face_data.json')
    
    try:
        # Check if we already have face data for this video
        if os.path.exists(output_path):
            # Check if video is newer than face data
            if not face_detector.should_process_video(video_path, output_path):
                logger.info("Using existing face data")
                with open(output_path, 'r') as f:
                    data = json.load(f)
                    if data and 'face_detections' in data:
                        return jsonify({
                            "status": "success", 
                            "message": "Using existing face detection data",
                            "cached": True
                        })
                    else:
                        logger.warning("Existing face data is invalid, reprocessing")
        
        # Process video if no data exists or video is newer
        success = face_detector.process_video(video_path, output_path)
        if success:
            return jsonify({
                "status": "success", 
                "message": "Video processed successfully",
                "cached": False
            })
        return jsonify({"status": "error", "message": "Failed to process video"}), 500
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/face_data', methods=['GET'])
def get_face_data():
    data_path = os.path.join(DATA_DIR, 'face_data.json')
    if not os.path.exists(data_path):
        return jsonify({"error": "Face detection data not found"}), 404
    
    try:
        with open(data_path, 'r') as f:
            data = json.load(f)
            if not data or 'face_detections' not in data:
                return jsonify({"error": "Invalid face detection data format"}), 500
            return jsonify(data)
    except json.JSONDecodeError:
        return jsonify({"error": "Face detection data is incomplete"}), 500
    except Exception as e:
        logger.error(f"Error reading face data: {str(e)}")
        return jsonify({"error": "Failed to read face detection data"}), 500

if __name__ == '__main__':
    # Start HLS conversion on startup (like your original code)
    threading.Thread(target=start_hls_conversion, daemon=True).start()
    
    app.run(host='0.0.0.0', port=5000, debug=False)