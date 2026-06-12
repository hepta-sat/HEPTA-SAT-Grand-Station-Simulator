#!/usr/bin/env python3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
import os
import socket
import sys
import webbrowser


ROOT = os.path.abspath(os.path.dirname(__file__))
PREFER_PORT = 8000
INDEX_FILE = "hepta_ground_station_ui_compact_v36_wider_azel_graph.html"


class HeptaRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def translate_path(self, path):
        translated = super().translate_path(path)
        root_real = os.path.realpath(ROOT)
        translated_real = os.path.realpath(translated)
        if not translated_real.startswith(root_real):
            return ROOT
        return translated

    def do_GET(self):
        if self.path == "/":
            self.path = "/" + INDEX_FILE
        return super().do_GET()


def find_port():
    for port in (PREFER_PORT, 0):
        try:
            server = ThreadingHTTPServer(("localhost", port), HeptaRequestHandler)
            return server
        except OSError:
            continue
    raise OSError("No available port")


def main():
    os.chdir(ROOT)
    mimetypes.add_type("application/javascript; charset=utf-8", ".js")
    mimetypes.add_type("text/html; charset=utf-8", ".html")
    mimetypes.add_type("application/json; charset=utf-8", ".json")

    try:
        server = find_port()
    except OSError as exc:
        print(f"Failed to start server: {exc}", file=sys.stderr)
        return 1

    host, port = server.server_address
    url = f"http://localhost:{port}/{INDEX_FILE}"
    print(f"Serving {ROOT} on {url}")
    print("Python fallback server is running. Use the UI connection button to select the XBee serial port.")

    if os.environ.get("HEPTA_NO_OPEN") != "1":
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
