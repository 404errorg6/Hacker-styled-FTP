from http.server import HTTPServer
from socketserver import ThreadingMixIn
try:
    from http.server import ThreadingHTTPServer
except ImportError:
    # Fallback for Python < 3.7
    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        pass
from .server import HackerHTTPHandler, get_lan_ip_address
import os
import sys


def run():
    print("Choose directory to serve:")
    print("1) Current directory")
    print("2) /storage/emulated/0 (Android default storage)")
    print("3) Custom path")
    choice = input("Enter choice (1/2/3): ").strip() or "2"

    if choice == '1':
        serve_path = '.'
    elif choice == '2':
        serve_path = '/storage/emulated/0'
    elif choice == '3':
        serve_path = input("Enter full custom path: ").strip()
        if serve_path == '':
            print("Empty path, exiting.")
            sys.exit(1)
    else:
        print("Invalid choice, exiting.")
        sys.exit(1)

    if not os.path.isdir(serve_path):
        print(f"Error: {serve_path} is not a directory.")
        sys.exit(1)

    port_input = input("Enter port number (default 8080): ").strip()
    port = int(port_input) if port_input.isdigit() else 8080
    os.chdir(os.path.abspath(serve_path))

    print(f"Serving directory: {os.getcwd()}")
    print(f"Starting server on {get_lan_ip_address()}:{port}...")
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, HackerHTTPHandler)

    ip = get_lan_ip_address()
    if ip.split(".")[0] == "127":
        ip = "localhost"

    print(f"Open in browser: http://{ip}:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == '__main__':
    run()
