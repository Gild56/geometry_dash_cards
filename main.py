from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import threading
import asyncio
import nest_asyncio
from app import main


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK - Bot is alive.")


def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Keep-alive server running on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()

    try:
        asyncio.run(main())
    except RuntimeError as e:
        print("Applying nest_asyncio due to RuntimeError:", e)
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
