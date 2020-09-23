from http.server import HTTPServer, SimpleHTTPRequestHandler

print("Hello world")
server_object = HTTPServer(server_address=('', 8080), RequestHandlerClass=SimpleHTTPRequestHandler)
server_object.serve_forever()
