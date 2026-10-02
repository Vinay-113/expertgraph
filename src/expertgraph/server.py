"""Loopback-only evidence explorer; issue content is never executable."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import joblib

from .data import digest, load_jsonl
from .retrieval import Engine


def load_system(root: Path):
    docs = load_jsonl(root / "data/corpus.jsonl")
    model_path = root / "artifacts/models/routing.joblib"
    if not model_path.exists():
        raise ValueError("Run expertgraph evaluate before opening the explorer")
    # Only load the artifact produced locally by our evaluator. Never accept uploaded pickle files.
    saved = joblib.load(model_path)
    if saved["corpus_sha256"] != digest(docs):
        raise ValueError("The model belongs to a different corpus; re-evaluation is required")
    return Engine(docs, root / "artifacts/cache"), saved["router"], saved["calibrator"]


def serve(root: Path, engine, router, calibrator, port: int = 8765):
    lock = threading.Lock()
    static = {"/": (root / "ui/index.html", "text/html; charset=utf-8"),
              "/app.js": (root / "ui/app.js", "text/javascript; charset=utf-8"),
              "/api/results": (root / "artifacts/results/results.json", "application/json"),
              "/api/validation": (root / "artifacts/validation-v1/results.json", "application/json"),
              "/comparison.png": (root / "artifacts/results/retrieval_comparison.png", "image/png")}

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, content, mime="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if self.path == "/api/health":
                self.send(200, json.dumps({"status": "ready", "documents": len(engine.docs)}).encode())
            elif self.path in static:
                path, mime = static[self.path]
                if path.exists():
                    self.send(200, path.read_bytes(), mime)
                else:
                    self.send(404, b'{"error":"Artifact not yet generated"}')
            else:
                self.send(404, b'{"error":"Not found"}')

        def do_POST(self):
            if self.path != "/api/query":
                self.send(404, b'{"error":"Not found"}')
                return
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
                self.send(403, b'{"error":"Cross-origin queries are disabled"}')
                return
            try:
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("Use application/json")
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 12000:
                    raise ValueError("Invalid request size")
                payload = json.loads(self.rfile.read(size))
                query = payload.get("query") if isinstance(payload, dict) else None
                if not isinstance(query, str):
                    raise ValueError("query must be a string")
                method = payload.get("method", "routed_hybrid")
                if not isinstance(method, str):
                    raise ValueError("method must be a string")
                with lock:
                    result = engine.report(query, router, calibrator, method=method)
                self.send(200, json.dumps(result).encode())
            except (ValueError, TypeError) as exc:
                self.send(400, json.dumps({"error": str(exc)}).encode())
            except Exception:
                self.send(500, b'{"error":"Retrieval failed; check the local terminal"}')

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"ExpertGraph is ready: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
