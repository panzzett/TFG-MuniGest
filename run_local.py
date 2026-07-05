"""Trabajo Fin de Grado en Ingenieria Informatica
Universidad Internacional de La Rioja (UNIR)
Prototipo de software de tramitacion de expedientes electronicos para administraciones locales
Autor: Carlos Galvez Reguera
Ano: 2026

Este archivo forma parte de este proyecto, desarrollado como
Trabajo Fin de Grado en Ingenieria Informatica de la UNIR.

Licencia: MIT

Lanzador local: Flask API en 5000 + servidor web estatico en 8000.

Soporta SSI <!--#include file="..." --> y reenvia /api/* a Flask.
"""
from __future__ import annotations

import http.server
import os
import re
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
API_PORT = 5000
WEB_PORT = 8000

os.environ.setdefault("FIRMA_ROOT", str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

SSI_RE = re.compile(rb'<!--#include\s+file="([^"]+)"\s*-->')

_CT = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".pdf": "application/pdf",
}


def _ctype(ext: str) -> str:
    return _CT.get(ext.lower(), "application/octet-stream")


def _render_ssi(path: Path, vistos: set[Path] | None = None) -> bytes:
    vistos = vistos or set()
    if path in vistos:
        return b""
    vistos.add(path)
    data = path.read_bytes()

    def sub(m: re.Match) -> bytes:
        inc = (WEB_ROOT / m.group(1).decode()).resolve()
        try:
            inc.relative_to(WEB_ROOT.resolve())
        except ValueError:
            return b""
        if inc.is_file():
            return _render_ssi(inc, vistos)
        return b""

    return SSI_RE.sub(sub, data)


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self, method: str) -> None:
        url = f"http://127.0.0.1:{API_PORT}{self.path}"
        body = None
        if "Content-Length" in self.headers:
            body = self.rfile.read(int(self.headers["Content-Length"]))
        req = urllib.request.Request(url, data=body, method=method)
        for h in self.headers:
            if h.lower() in ("host", "content-length"):
                continue
            req.add_header(h, self.headers[h])
        try:
            with urllib.request.urlopen(req) as resp:
                out = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding", "connection", "content-length"):
                        continue
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)
        except urllib.error.HTTPError as e:
            out = e.read()
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() in ("transfer-encoding", "connection", "content-length"):
                    continue
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
        except Exception as e:
            self.send_error(502, f"API no accesible: {e}")

    def _enviar(self, data: bytes, ctype: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _static(self) -> None:
        ruta = self.path.split("?", 1)[0].split("#", 1)[0]
        if ruta in ("", "/"):
            ruta = "/index.html"
        archivo = (WEB_ROOT / ruta.lstrip("/")).resolve()
        try:
            archivo.relative_to(WEB_ROOT.resolve())
        except ValueError:
            self.send_error(403)
            return
        if archivo.is_dir():
            archivo = archivo / "index.html"
        if not archivo.is_file():
            archivo = WEB_ROOT / "index.html"
        ext = archivo.suffix.lower()
        if ext == ".html":
            data = _render_ssi(archivo)
        else:
            data = archivo.read_bytes()
        self._enviar(data, _ctype(ext))

    def do_GET(self):
        if self.path.startswith("/api/"):
            self._proxy("GET")
        else:
            self._static()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self._proxy("POST")
        else:
            self.send_error(405)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self._proxy("DELETE")
        else:
            self.send_error(405)

    def do_PUT(self):
        if self.path.startswith("/api/"):
            self._proxy("PUT")
        else:
            self.send_error(405)

    def do_PATCH(self):
        if self.path.startswith("/api/"):
            self._proxy("PATCH")
        else:
            self.send_error(405)

    def log_message(self, *a, **k):
        pass


class Servidor(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _arrancar_api() -> None:
    from app import app  # noqa
    app.run(host="127.0.0.1", port=API_PORT, debug=False, use_reloader=False)


def main() -> None:
    print("=" * 60)
    print("  FIRMA PDF con AutoFirma  -  modo local")
    print("=" * 60)

    threading.Thread(target=_arrancar_api, daemon=True).start()
    time.sleep(1.5)

    print(f"  Web: http://localhost:{WEB_PORT}")
    print(f"  API: http://127.0.0.1:{API_PORT}/api/  (interno)")
    print("  Ctrl+C para detener.")
    print("=" * 60)

    srv = Servidor(("0.0.0.0", WEB_PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")


if __name__ == "__main__":
    main()
