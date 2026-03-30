#!/usr/bin/env python3
import argparse
import http.server
import json
import socketserver
from functools import partial
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
VENUES_PATH = PROJECT_ROOT / "data" / "venues.json"


class ReusableTcpServer(socketserver.TCPServer):
    allow_reuse_address = True


class AppRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        self.project_directory = Path(directory or ".").resolve()
        super().__init__(*args, directory=str(self.project_directory), **kwargs)

    def do_GET(self):
        if self.path == "/api/venues":
            self.serve_venues()
            return

        super().do_GET()

    def serve_venues(self):
        try:
            payload = VENUES_PATH.read_text(encoding="utf-8")
            venues = json.loads(payload)
        except FileNotFoundError:
            self.send_error(500, "venues.json not found")
            return
        except json.JSONDecodeError:
            self.send_error(500, "venues.json is invalid")
            return

        body = json.dumps(
            {
                "venues": venues,
                "count": len(venues),
            },
            ensure_ascii=False,
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Serve the afterparty izakaya finder.")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8123, help="Port to bind")
    parser.add_argument("--directory", default=".", help="Directory to serve")
    args = parser.parse_args()

    handler_class = partial(AppRequestHandler, directory=args.directory)

    with ReusableTcpServer((args.host, args.port), handler_class) as httpd:
        print(f"Serving {args.directory} at http://{args.host}:{args.port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
