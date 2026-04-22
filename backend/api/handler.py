"""
Vercel handler that properly inherits from BaseHTTPRequestHandler
"""
import sys
import os
from http.server import BaseHTTPRequestHandler
import json

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

# Set environment variables for Vercel
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

class Handler(BaseHTTPRequestHandler):
    """
    Proper HTTP request handler that inherits from BaseHTTPRequestHandler
    This fixes the issubclass() TypeError
    """
    
    def do_GET(self):
        """Handle GET requests"""
        self.process_request()
    
    def do_POST(self):
        """Handle POST requests"""
        self.process_request()
    
    def do_PUT(self):
        """Handle PUT requests"""
        self.process_request()
    
    def do_DELETE(self):
        """Handle DELETE requests"""
        self.process_request()
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def send_cors_headers(self):
        """Send CORS headers"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Content-Type', 'application/json')
    
    def process_request(self):
        """Process HTTP requests without recursion"""
        try:
            # Set CORS headers
            self.send_response(200)
            self.send_cors_headers()
            self.end_headers()
            
            # Get the path
            path = self.path.split('?')[0]  # Remove query parameters
            
            # Handle different endpoints
            if path == '/':
                response = {"message": "PhatagiAI Backend is running!", "status": "healthy"}
            elif path == '/health':
                response = {"status": "healthy", "message": "Backend is working"}
            elif path == '/test':
                response = {"message": "Backend is working!", "cors_working": True, "status": "healthy"}
            elif path == '/status':
                response = {"status": "healthy", "message": "Simple backend is running", "version": "1.0.0"}
            elif path.startswith('/auth/'):
                if path == '/auth/login':
                    # Mock login response
                    response = {
                        "access_token": "mock_token_12345",
                        "token_type": "bearer",
                        "user": {
                            "email": "test@example.com",
                            "username": "testuser"
                        }
                    }
                elif path == '/auth/register':
                    # Mock register response
                    response = {
                        "message": "User registered successfully",
                        "user": {
                            "username": "testuser",
                            "email": "test@example.com"
                        }
                    }
                else:
                    response = {"message": "Auth endpoint working", "status": "healthy"}
            elif path.startswith('/api/'):
                if path == '/api/conversations':
                    # Return empty conversations array for now
                    response = []
                elif path == '/api/projects':
                    # Return empty projects array for now
                    response = []
                else:
                    response = {"message": "API endpoint working", "status": "healthy"}
            elif path.startswith('/openai/'):
                # Handle OpenAI chat endpoints
                if path.endswith('/chat'):
                    # Mock chat response
                    response = {
                        "message": "Chat endpoint working",
                        "status": "healthy",
                        "model": path.split('/')[2],
                        "response": "This is a mock response. The full backend with database is not available in this simple handler."
                    }
                else:
                    response = {"message": "OpenAI endpoint working", "status": "healthy"}
            elif path.startswith('/xai/'):
                # Handle XAI chat endpoints
                if path.endswith('/chat'):
                    response = {
                        "message": "XAI chat endpoint working",
                        "status": "healthy",
                        "model": path.split('/')[2],
                        "response": "This is a mock response. The full backend with database is not available in this simple handler."
                    }
                else:
                    response = {"message": "XAI endpoint working", "status": "healthy"}
            elif path.startswith('/qwen/'):
                # Handle Qwen chat endpoints
                if path.endswith('/chat'):
                    response = {
                        "message": "Qwen chat endpoint working",
                        "status": "healthy",
                        "model": path.split('/')[2],
                        "response": "This is a mock response. The full backend with database is not available in this simple handler."
                    }
                else:
                    response = {"message": "Qwen endpoint working", "status": "healthy"}
            elif path.startswith('/moonshot/'):
                # Handle Moonshot chat endpoints
                if path.endswith('/chat'):
                    response = {
                        "message": "Moonshot chat endpoint working",
                        "status": "healthy",
                        "model": path.split('/')[2],
                        "response": "This is a mock response. The full backend with database is not available in this simple handler."
                    }
                else:
                    response = {"message": "Moonshot endpoint working", "status": "healthy"}
            else:
                response = {"message": "Endpoint working", "status": "healthy", "path": path}
            
            # Send JSON response
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            # Handle errors
            self.send_response(500)
            self.send_cors_headers()
            self.end_headers()
            error_response = {"error": f"Backend error: {str(e)}"}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

# Create the handler instance
handler = Handler
