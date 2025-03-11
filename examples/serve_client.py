import http.server
import socketserver
import urllib.request
import urllib.error
import os
import json
import sys

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
MCP_SERVER_URL = "http://localhost:3000"

class ProxyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
        
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
        
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
        
    def do_GET(self):
        if self.path.startswith('/mcp/'):
            # This is a request to proxy to the MCP server
            mcp_path = self.path[4:]  # Remove '/mcp' prefix
            full_url = f"{MCP_SERVER_URL}{mcp_path}"
            print(f"Proxying GET request to: {full_url}")
            
            try:
                # Forward the request to the MCP server
                req = urllib.request.Request(full_url, method="GET")
                
                # Copy headers from original request
                for header, value in self.headers.items():
                    if header.lower() not in ['host', 'connection']:
                        req.add_header(header, value)
                
                with urllib.request.urlopen(req) as response:
                    # Copy response code
                    self.send_response(response.status)
                    
                    # Copy response headers
                    for header, value in response.getheaders():
                        if header.lower() not in ['transfer-encoding', 'connection']:
                            self.send_header(header, value)
                    
                    self.end_headers()
                    
                    # Copy response body
                    self.wfile.write(response.read())
            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Error: {e.code} {e.reason}".encode('utf-8'))
                print(f"Proxy error: {e.code} {e.reason}")
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))
                print(f"Proxy error: {e}")
        else:
            # Not a proxy request, serve local files
            return super().do_GET()
            
    def do_POST(self):
        if self.path.startswith('/mcp/'):
            # This is a request to proxy to the MCP server
            mcp_path = self.path[4:]  # Remove '/mcp' prefix
            full_url = f"{MCP_SERVER_URL}{mcp_path}"
            
            try:
                # Get the body content
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length) if content_length > 0 else None
                
                print(f"Proxying POST request to: {full_url}")
                if post_data:
                    print(f"With data: {post_data.decode('utf-8')}")
                
                # Explicitly set the Content-Type header for POST requests
                headers = {}
                for header, value in self.headers.items():
                    if header.lower() not in ['host', 'connection']:
                        headers[header] = value
                
                # Ensure Content-Type is set for JSON data
                if not 'content-type' in [h.lower() for h in headers]:
                    headers['Content-Type'] = 'application/json'
                
                # Create a properly formatted request with explicit headers
                req = urllib.request.Request(
                    url=full_url,
                    data=post_data,
                    headers=headers,
                    method="POST"
                )
                
                # Open the request with proper error handling
                try:
                    with urllib.request.urlopen(req) as response:
                        # Copy response code
                        self.send_response(response.status)
                        
                        # Copy response headers
                        for header, value in response.getheaders():
                            if header.lower() not in ['transfer-encoding', 'connection']:
                                self.send_header(header, value)
                        
                        self.end_headers()
                        
                        # Copy response body
                        response_data = response.read()
                        self.wfile.write(response_data)
                        print(f"Proxy response: {response.status}")
                except urllib.error.HTTPError as e:
                    self.send_response(e.code)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(f"Error: {e.code} {e.reason}".encode('utf-8'))
                    print(f"Proxy error: {e.code} {e.reason}")
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))
                print(f"Proxy error: {e}")
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Not Found")

if __name__ == "__main__":
    print(f"Starting server at http://localhost:{PORT}")
    print(f"Proxying MCP requests to {MCP_SERVER_URL}")
    try:
        with socketserver.TCPServer(("", PORT), ProxyHTTPRequestHandler) as httpd:
            print(f"Server started. Open http://localhost:{PORT}/index.html in your browser")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped by user")
    except Exception as e:
        print(f"Server error: {e}") 