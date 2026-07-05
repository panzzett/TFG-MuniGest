"""Trabajo Fin de Grado en Ingenieria Informatica
Universidad Internacional de La Rioja (UNIR)
Prototipo de software de tramitacion de expedientes electronicos para administraciones locales
Autor: Carlos Galvez Reguera
Ano: 2026

Este archivo forma parte de este proyecto, desarrollado como
Trabajo Fin de Grado en Ingenieria Informatica de la UNIR.

Licencia: MIT

Launcher para empaquetar la aplicacion en un .exe con PyInstaller.

Arranca la API Flask en :5000 y el servidor web en :8000, abre el
navegador en http://localhost:8000 y deja la consola viva hasta Ctrl+C.

Espera encontrar las carpetas `api/`, `web/` y `data/` al lado del .exe
(o del propio script si se ejecuta sin congelar).
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE = _base_dir()
os.environ["FIRMA_ROOT"] = str(BASE)
sys.path.insert(0, str(BASE / "api"))
sys.path.insert(0, str(BASE))

import run_local  # noqa: E402


def _abrir_navegador() -> None:
    time.sleep(2.5)
    try:
        webbrowser.open(f"http://localhost:{run_local.WEB_PORT}")
    except Exception:
        pass


if __name__ == "__main__":
    threading.Thread(target=_abrir_navegador, daemon=True).start()
    run_local.main()
