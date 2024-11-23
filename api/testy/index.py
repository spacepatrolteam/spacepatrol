from http.server import BaseHTTPRequestHandler
 
class handler(BaseHTTPRequestHandler):
 
    def testy(self):
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        self.wfile.write('Hello, world testy!'.encode('utf-8'))
        return