from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os
import subprocess
import threading
import logging
import time

app = Flask(__name__)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), 'Uploads')
STREAMS_DIR = os.path.join(os.path.dirname(__file__), 'streams')
VIDEO_FILENAME = 'sample.mp4'

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STREAMS_DIR, exist_ok=True)

def convert_to_hls():
    video_path = os.path.join(UPLOADS_DIR, VIDEO_FILENAME)
    stream_output_dir = os.path.join(STREAMS_DIR, 'sample')
    os.makedirs(stream_output_dir, exist_ok=True)

    m3u8_path = os.path.join(stream_output_dir, 'playlist.m3u8')

    # Clear old segments to start fresh
    if os.path.exists(stream_output_dir):
        for file in os.listdir(stream_output_dir):
            os.remove(os.path.join(stream_output_dir, file))

    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return None

    # FFmpeg command for continuous HLS segment generation
    ffmpeg_cmd = [
        'ffmpeg',
        '-re',  # Real-time encoding
        '-i', video_path,
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-b:v', '1.5M',  # Lower bitrate for faster encoding
        '-b:a', '128k',
        '-f', 'hls',
        '-hls_time', '6',  # 6-second segments for quicker availability
        '-hls_list_size', '0',  # Include all segments
        '-hls_segment_filename', os.path.join(stream_output_dir, 'segment_%03d.ts'),
        '-hls_flags', 'delete_segments+append_list',  # Delete old segments, append new ones
        '-hls_segment_type', 'mpegts',  # Ensure compatibility
        m3u8_path
    ]

    logger.debug(f"Starting FFmpeg: {' '.join(ffmpeg_cmd)}")
    try:
        # Run FFmpeg in background
        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # Monitor FFmpeg output
        def log_ffmpeg_output():
            while process.poll() is None:
                line = process.stderr.readline()
                if line:
                    logger.debug(f"FFmpeg: {line.strip()}")
            _, stderr = process.communicate()
            if process.returncode != 0:
                logger.error(f"FFmpeg exited with error: {stderr}")
            else:
                logger.info("FFmpeg completed conversion")

        threading.Thread(target=log_ffmpeg_output, daemon=True).start()

        # Wait for initial playlist creation (up to 60 seconds)
        for _ in range(60):
            if os.path.exists(m3u8_path) and os.path.getsize(m3u8_path) > 0:
                logger.info(f"Playlist created: {m3u8_path}")
                return f'/streams/sample/playlist.m3u8'
            time.sleep(1)
        logger.error("Timeout waiting for playlist creation")
        return None
    except Exception as e:
        logger.error(f"FFmpeg setup failed: {str(e)}")
        return None

@app.route('/api/get_video', methods=['GET'])
def get_video():
    hls_path = f'/streams/sample/playlist.m3u8'
    m3u8_full_path = os.path.join(STREAMS_DIR, 'sample', 'playlist.m3u8')
    if os.path.exists(m3u8_full_path) and os.path.getsize(m3u8_full_path) > 0:
        return jsonify({"video_url": f"http://localhost:5000{hls_path}"})
    else:
        logger.warning("HLS stream not ready")
        return jsonify({"error": "HLS stream not ready yet, please try again in a moment"}), 503

@app.route('/streams/sample/<path:filename>')
def serve_stream(filename):
    logger.debug(f"Serving file: {filename}")
    return send_from_directory(os.path.join(STREAMS_DIR, 'sample'), filename)

# Start HLS conversion on app startup
def start_hls_conversion():
    logger.info("Initiating HLS conversion")
    result = convert_to_hls()
    if not result:
        logger.error("Failed to start HLS conversion")

if __name__ == '__main__':
    threading.Thread(target=start_hls_conversion, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=True)