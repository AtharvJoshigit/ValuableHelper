
import http.server
import socketserver
import json
import os
import threading
from urllib.parse import urlparse, parse_qs

PORT = 8000
DIRECTORY = "src"

class ValHHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Serve static files correctly
        if self.path == '/':
            self.path = '/index.html'
        
        # Handle static CSS/JS paths
        if self.path.startswith('/static/'):
            self.path = self.path.replace('/static/', '/')
            
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        if self.path == '/chat':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            user_message = data.get('message', '')
            print(f"User said: {user_message}")

            # Here we would normally call the Agent Logic
            # For now, we simulate a response to prove the UI works
            response_text = f"I heard you say: '{user_message}'. My backend is connected."
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*') # Allow local dev
            self.end_headers()
            self.wfile.write(json.dumps({'response': response_text}).encode('utf-8'))
        else:
            self.send_error(404, "Endpoint not found")

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

# Set the working directory to src so it finds index.html
os.chdir(os.path.join(os.getcwd(), 'src'))

with socketserver.TCPServer(("", PORT), ValHHandler) as httpd:
    print(f"Serving ValH UI at http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
