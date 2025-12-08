
import http.server
import socketserver
import subprocess
import os
import json
import sys
from pathlib import Path

# Configuration
PORT = 8080
SCRIPT_DIR = Path(__file__).parent.absolute()
ROOT_DIR = SCRIPT_DIR.parent
RUN_BOT_SCRIPT = SCRIPT_DIR / "run_bot.bat"

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/start':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                print(f"Received start request. Launching {RUN_BOT_SCRIPT}...")
                
                # Launch run_bot.bat in a new independent window
                # 'start' command in Windows cmd opens a new window
                cmd = f'start "Transcription Worker (GPU)" "{RUN_BOT_SCRIPT}"'
                
                subprocess.Popen(cmd, shell=True)
                
                response = {"status": "success", "message": "Transcription worker started in new window"}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
            except Exception as e:
                print(f"Error launching worker: {e}")
                response = {"status": "error", "message": str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_error(404, "Endpoint not found")

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode('utf-8'))
        else:
            self.send_error(404, "Endpoint not found")

def run(port=PORT):
    # Ensure we are in the correct directory context if needed
    print(f"Host Listener running on port {port}...")
    print(f"Target script: {RUN_BOT_SCRIPT}")
    
    with socketserver.TCPServer(("", port), RequestHandler) as httpd:
        print("Ready to receive start signals.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down listener.")

if __name__ == "__main__":
    run()
