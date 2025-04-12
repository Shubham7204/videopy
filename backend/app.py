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

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
STREAMS_DIR = os.path.join(os.path.dirname(__file__), 'streams')
VIDEO_FILENAME = 'sample.mp4'

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STREAMS_DIR, exist_ok=True)

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

    # Simplified FFmpeg command
    ffmpeg_cmd = [
        'ffmpeg',
        '-i', video_path,
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-b:v', '800k',
        '-b:a', '128k',
        '-f', 'hls',
        '-hls_time', '6',
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

if __name__ == '__main__':
    threading.Thread(target=start_hls_conversion, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False)