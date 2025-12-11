"""
Host Listener Service for Docker Transcription Trigger

This service runs on the Windows host and listens for HTTP requests
from the transcription API container. When triggered, it executes the
docker-compose command to start the transcription worker.

Usage:
    python host_listener.py

The service will listen on http://localhost:8080
"""
import subprocess
import logging
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app)  # Allow requests from Docker containers

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'transcription-trigger-listener',
        'version': '1.0.0'
    })


@app.route('/start', methods=['POST'])
def start_transcription():
    """
    Trigger transcription worker in Docker.
    
    This endpoint is called by the transcription API when the user
    clicks the "Run Transcription" button.
    """
    try:
        logger.info("Received transcription start request")
        
        # Execute docker-compose command
        logger.info(f"Executing docker-compose in: {PROJECT_ROOT}")
        
        result = subprocess.run(
            ['docker-compose', 'run', '--rm', 'transcription-worker'],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=7200  # 2 hour timeout for long transcriptions
        )
        
        if result.returncode == 0:
            logger.info("Transcription worker completed successfully")
            return jsonify({
                'status': 'success',
                'message': 'Transcription worker completed successfully'
            })
        else:
            logger.error(f"Transcription worker failed: {result.stderr}")
            return jsonify({
                'status': 'error',
                'message': f'Transcription worker failed: {result.stderr}'
            }), 500
            
    except subprocess.TimeoutExpired:
        logger.error("Transcription worker timed out after 2 hours")
        return jsonify({
            'status': 'error',
            'message': 'Transcription timed out after 2 hours'
        }), 500
        
    except Exception as e:
        logger.error(f"Error starting transcription: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/status', methods=['GET'])
def get_status():
    """Get current transcription status."""
    # TODO: Could enhance this to check if transcription-worker container is running
    return jsonify({
        'listener_running': True,
        'project_root': str(PROJECT_ROOT)
    })


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("Starting Transcription Trigger Listener")
    logger.info("=" * 60)
    logger.info(f"Project root: {PROJECT_ROOT}")
    logger.info("Listening on: http://localhost:8080")
    logger.info("Endpoints:")
    logger.info("  - GET  /health  - Health check")
    logger.info("  - POST /start   - Start transcription worker")
    logger.info("  - GET  /status  - Get listener status")
    logger.info("=" * 60)
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=8080,
        debug=False  # Set to False for production
    )
