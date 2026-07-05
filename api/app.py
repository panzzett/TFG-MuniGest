"""Trabajo Fin de Grado en Ingenieria Informatica
Universidad Internacional de La Rioja (UNIR)
Prototipo de software de tramitacion de expedientes electronicos para administraciones locales
Autor: Carlos Galvez Reguera
Ano: 2026

Este archivo forma parte de este proyecto, desarrollado como
Trabajo Fin de Grado en Ingenieria Informatica de la UNIR.

Licencia: MIT

API Flask: gestion de expedientes con firma AutoFirma.

Cada expediente tiene un ID autoincremental (contador global), una referencia,
descripcion, lista de pasos administrativos, posibles archivos adjuntos
(los .docx se convierten a PDF al subir) y un estado:
  - borrador           -> no se ha generado el PDF resumen
  - pdf_generado       -> existe PDF resumen pero no firmado
  - firmado            -> PDF firmado con AutoFirma (no se puede borrar)

Endpoints principales:
  POST   /api/registro                                 crear usuario
  POST   /api/login                                    iniciar sesion
  POST   /api/logout
  GET    /api/me

  GET    /api/pasos                                    catalogo de pasos administrativos
  GET    /api/expedientes?q=&id=                       listar/buscar
  POST   /api/expedientes                              crear
  GET    /api/expedientes/<id>                         detalle
  PUT    /api/expedientes/<id>                         editar (solo borrador o pdf_generado)
  DELETE /api/expedientes/<id>                         borrar (no si firmado)

  POST   /api/expedientes/<id>/adjuntos                subir adjunto (.pdf, .docx)
  DELETE /api/expedientes/<id>/adjuntos/<n>            eliminar adjunto
  GET    /api/expedientes/<id>/adjuntos/<n>            descargar adjunto

  POST   /api/expedientes/<id>/generar                 generar PDF resumen
  GET    /api/expedientes/<id>/pdf                     descargar PDF resumen
  POST   /api/expedientes/<id>/firmar                  firmar PDF con AutoFirma
  GET    /api/expedientes/<id>/firmado                 descargar PDF firmado

  GET    /api/autofirma/estado
  GET    /api/certificados
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt
from flask import Flask, g, jsonify, request, send_file
from fpdf import FPDF
from fpdf.enums import XPos, YPos

ROOT = Path(os.environ.get("FIRMA_ROOT", Path(__file__).resolve().parent.parent))
DATA_DIR = ROOT / "data"
EXP_DIR = DATA_DIR / "expedientes"
DOC_DIR = DATA_DIR / "documentos"
AUTH_FILE = DATA_DIR / "auth.json"
EXP_FILE = DATA_DIR / "expedientes.json"
DOC_FILE = DATA_DIR / "documentos.json"

EXP_DIR.mkdir(parents=True, exist_ok=True)
DOC_DIR.mkdir(parents=True, exist_ok=True)

_LOCK = threading.RLock()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

# Catalogo de pasos administrativos (lista emergente del formulario)
PASOS_ADMINISTRATIVOS = [
    "Inicio del expediente",
    "Solicitud presentada",
    "Subsanacion de defectos",
    "Revision documental",
    "Informe tecnico",
    "Informe juridico",
    "Propuesta de resolucion",
    "Audiencia al interesado",
    "Resolucion",
    "Notificacion al interesado",
    "Recursos administrativos",
    "Archivo del expediente",
]

ESTADO_BORRADOR = "borrador"
ESTADO_PDF = "pdf_generado"
ESTADO_FIRMADO = "firmado"


# ============================================================ almacen JSON
def _cargar(path: Path, defecto: dict) -> dict:
    if not path.is_file():
        return dict(defecto)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(defecto)


def _guardar(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _cargar_auth() -> dict:
    return _cargar(AUTH_FILE, {"usuarios": {}, "tokens": {}})


def _guardar_auth(data: dict) -> None:
    _guardar(AUTH_FILE, data)


def _cargar_exp() -> dict:
    return _cargar(EXP_FILE, {"contador": 0, "items": []})


def _guardar_exp(data: dict) -> None:
    _guardar(EXP_FILE, data)


def _cargar_doc() -> dict:
    return _cargar(DOC_FILE, {"contador": 0, "items": []})


def _guardar_doc(data: dict) -> None:
    _guardar(DOC_FILE, data)


def _doc_dir(id_: int) -> Path:
    d = DOC_DIR / str(id_)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _doc_publico(d: dict) -> dict:
    eid = d["id"]
    out = dict(d)
    out["pdf_url"] = f"/api/documentos/{eid}/pdf" if d.get("pdf") else None
    out["firmado_url"] = f"/api/documentos/{eid}/firmado" if d.get("firmado") else None
    return out


def _purgar_tokens(data: dict) -> None:
    ahora = datetime.utcnow()
    expirados = [t for t, v in data.get("tokens", {}).items()
                 if datetime.fromisoformat(v["exp"]) < ahora]
    for t in expirados:
        data["tokens"].pop(t, None)


# ================================================================ sesiones
def _validar_usuario(nombre: str) -> bool:
    if not nombre or len(nombre) > 32:
        return False
    return all(c.isalnum() or c in "_-." for c in nombre)


def _sesion_actual() -> str | None:
    token = request.cookies.get("sesion") or request.headers.get("X-Sesion")
    if not token:
        return None
    with _LOCK:
        data = _cargar_auth()
        _purgar_tokens(data)
        info = data.get("tokens", {}).get(token)
        if not info:
            return None
        return info.get("usuario")


def _requiere_login():
    usuario = _sesion_actual()
    if not usuario:
        return None, (jsonify({"error": "no autenticado"}), 401)
    g.usuario = usuario
    return usuario, None


# ================================================================ AutoFirma
def _localizar_autofirma() -> str | None:
    ruta_env = os.environ.get("AUTOFIRMA_PATH")
    if ruta_env and Path(ruta_env).is_file():
        return ruta_env
    candidatos = [
        r"C:\Program Files\AutoFirma\AutoFirma\AutoFirma.exe",
        r"C:\Program Files (x86)\AutoFirma\AutoFirma\AutoFirma.exe",
        r"C:\Program Files\AutoFirma\AutoFirma.exe",
        "/usr/bin/autofirma",
        "/Applications/AutoFirma.app/Contents/MacOS/AutoFirma",
    ]
    for c in candidatos:
        if Path(c).is_file():
            return c
    return shutil.which("AutoFirma") or shutil.which("autofirma")


def _listar_certificados_windows() -> list[dict]:
    if os.name != "nt":
        return []
    ps = (
        "Get-ChildItem -Path Cert:\\CurrentUser\\My | "
        "Where-Object { $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) } | "
        "ForEach-Object { [PSCustomObject]@{ "
        "Subject=$_.Subject; Issuer=$_.Issuer; "
        "Thumbprint=$_.Thumbprint; NotAfter=$_.NotAfter.ToString('o') } } | "
        "ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return []
    salida = (proc.stdout or "").strip()
    if not salida:
        return []
    try:
        data = json.loads(salida)
    except Exception:
        return []
    if isinstance(data, dict):
        data = [data]
    out = []
    for c in data:
        subj = c.get("Subject") or ""
        cn = subj
        for parte in subj.split(","):
            p = parte.strip()
            if p.upper().startswith("CN="):
                cn = p[3:]
                break
        out.append({
            "nombre": cn, "subject": subj,
            "issuer": c.get("Issuer") or "",
            "thumbprint": (c.get("Thumbprint") or "").upper(),
            "expira": c.get("NotAfter") or "",
        })
    return out


def _firmar_pdf(pdf_in: Path, pdf_out: Path, thumbprint: str = "") -> tuple[bool, str]:
    exe = _localizar_autofirma()
    if not exe:
        return False, "AutoFirma no esta instalado en el sistema"
    cmd = [exe, "sign", "-i", str(pdf_in), "-o", str(pdf_out),
           "-format", "pades"]
    # Almacen del SO. AutoFirma espera los nombres en minusculas.
    # Override posible con variable de entorno AUTOFIRMA_STORE.
    store_def = "windows" if os.name == "nt" else (
        "mac" if sys.platform == "darwin" else "mozilla")
    store = (os.environ.get("AUTOFIRMA_STORE") or store_def).strip()
    cmd += ["-store", store]
    if thumbprint:
        cmd += ["-filter", f"thumbprint:{thumbprint.strip()}"]
    else:
        # Sin filtro hay que pedir explicitamente el dialogo grafico para
        # que el usuario pueda elegir el certificado.
        cmd += ["-certgui"]

    # En Windows 11 24H2 wmic.exe se elimina por defecto; AutoFirma lo usa para
    # detectar HiDPI. Aseguramos que la ruta clasica este en PATH por si existe,
    # y que el subproceso lo herede.
    env = os.environ.copy()
    if os.name == "nt":
        for d in (r"C:\Windows\System32\wbem", r"C:\Windows\System32"):
            if d not in env.get("PATH", "") and Path(d).is_dir():
                env["PATH"] = d + os.pathsep + env.get("PATH", "")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=300, env=env)
    except subprocess.TimeoutExpired:
        return False, "AutoFirma tardo demasiado (timeout 5 min)"
    except Exception as e:
        return False, f"Error al lanzar AutoFirma: {e}"

    # Si el PDF firmado existe y tiene contenido, lo damos por bueno aunque
    # AutoFirma haya escrito advertencias en stderr.
    if pdf_out.is_file() and pdf_out.stat().st_size > 0:
        return True, "ok"

    salidas_low = ((proc.stderr or "") + "\n" + (proc.stdout or "")).lower()

    # Si el filtro por huella coincide con varios certificados (cert duplicado
    # en distintos almacenes), reintentamos mostrando el dialogo de seleccion
    # limitado a los certificados que casan con el filtro.
    if thumbprint and ("mas de un certificado" in salidas_low
                       or "more than one certificate" in salidas_low):
        cmd_retry = list(cmd)
        if "-certgui" not in cmd_retry:
            cmd_retry.append("-certgui")
        try:
            proc = subprocess.run(cmd_retry, capture_output=True, text=True,
                                  timeout=300, env=env)
        except subprocess.TimeoutExpired:
            return False, "AutoFirma tardo demasiado (timeout 5 min)"
        except Exception as e:
            return False, f"Error al lanzar AutoFirma: {e}"
        if pdf_out.is_file() and pdf_out.stat().st_size > 0:
            return True, "ok"
        salidas_low = ((proc.stderr or "") + "\n" + (proc.stdout or "")).lower()

    # Mensaje amable y unico para la falta de certificados.
    if "no se han encontrado certificados" in salidas_low \
            or "no certificate" in salidas_low:
        return False, "Certificados no encontrados"

    # Construir mensaje filtrando advertencias inocuas sobre wmic / HDPI.
    salidas = ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()
    lineas = [
        l for l in salidas.splitlines()
        if l.strip() and "wmic" not in l.lower() and "hdpimanager" not in l.lower()
    ]
    msg = "\n".join(lineas).strip()
    if not msg:
        msg = ("AutoFirma no genero el PDF firmado. "
               "Posibles causas: no se selecciono certificado o se cancelo el dialogo.")
    return False, f"Firma cancelada o fallida: {msg[:400]}"


# ====================================================== Conversion DOCX->PDF
def _docx_a_pdf(docx_path: Path, pdf_path: Path) -> tuple[bool, str]:
    """Intenta convertir DOCX a PDF con docx2pdf (Word) o LibreOffice."""
    # 1) docx2pdf (requiere Microsoft Word instalado)
    try:
        from docx2pdf import convert  # type: ignore
        try:
            convert(str(docx_path), str(pdf_path))
            if pdf_path.is_file():
                return True, "ok"
        except Exception as e:
            err1 = str(e)
        else:
            err1 = "docx2pdf no genero el PDF"
    except Exception:
        err1 = "docx2pdf no disponible"

    # 2) LibreOffice / soffice headless
    soffice = (shutil.which("soffice") or shutil.which("libreoffice"))
    if not soffice:
        for c in (r"C:\Program Files\LibreOffice\program\soffice.exe",
                  r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                  "/usr/bin/soffice", "/usr/bin/libreoffice"):
            if Path(c).is_file():
                soffice = c
                break
    if soffice:
        try:
            subprocess.run(
                [soffice, "--headless", "--norestore", "--nologo",
                 "--convert-to", "pdf", "--outdir", str(pdf_path.parent),
                 str(docx_path)],
                capture_output=True, text=True, timeout=120, check=True,
            )
            generado = pdf_path.parent / (docx_path.stem + ".pdf")
            if generado.is_file():
                if generado != pdf_path:
                    generado.replace(pdf_path)
                return True, "ok"
            return False, "LibreOffice no genero el PDF"
        except subprocess.CalledProcessError as e:
            return False, f"LibreOffice fallo: {e.stderr or e.stdout}"
        except Exception as e:
            return False, f"LibreOffice fallo: {e}"

    return False, ("No se pudo convertir el DOCX a PDF. "
                   "Instala Microsoft Word (con docx2pdf) o LibreOffice.")


# ==================================================== Generar PDF expediente
def _generar_pdf_expediente(exp: dict, destino: Path) -> None:
    def _l1(s: str) -> str:
        return (s or "").encode("latin-1", "replace").decode("latin-1")

    def mc(texto: str, h: float = 6) -> None:
        # Tras multi_cell, en fpdf2 el cursor queda a la derecha; lo devolvemos
        # al margen izquierdo para que la siguiente celda se pinte bien.
        pdf.multi_cell(0, h, _l1(texto), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Cabecera
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, _l1(f"Expediente N.o {exp['id']}"), ln=True)
    pdf.set_draw_color(120, 120, 120)
    pdf.set_line_width(0.4)
    y = pdf.get_y()
    pdf.line(10, y, 200, y)
    pdf.ln(4)

    # Metadatos
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, _l1(f"Creado por: {exp.get('usuario', '')}"), ln=True)
    pdf.cell(0, 6, _l1(f"Fecha de creacion: {exp.get('fecha_creacion', '')}"), ln=True)
    pdf.cell(0, 6, _l1(f"Ultima modificacion: {exp.get('fecha_modificacion', '')}"), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Referencia
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, _l1("Referencia"), ln=True)
    pdf.set_font("Helvetica", "", 11)
    mc(exp.get("referencia") or "-")
    pdf.ln(2)

    # Descripcion
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, _l1("Descripcion"), ln=True)
    pdf.set_font("Helvetica", "", 11)
    mc(exp.get("descripcion") or "-")
    pdf.ln(2)

    # Pasos administrativos
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, _l1("Pasos administrativos"), ln=True)
    pasos = _normalizar_pasos(exp.get("pasos"))
    if pasos:
        for i, p in enumerate(pasos, 1):
            pdf.set_font("Helvetica", "B", 11)
            mc(f"{i}. {p['nombre']}")
            pdf.set_font("Helvetica", "", 10)
            docs = p.get("documentos") or []
            if docs:
                for d in docs:
                    mc(f"     - {d.get('nombre_original') or d.get('archivo','')}", h=5)
            else:
                pdf.set_text_color(130, 130, 130)
                mc("     (sin documentos)", h=5)
                pdf.set_text_color(0, 0, 0)
            pdf.ln(1)
    else:
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 6, _l1("(sin pasos)"), ln=True)
    pdf.ln(2)

    # Pie de firma
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(110, 110, 110)
    pdf.cell(0, 6, _l1("Documento pendiente de firma electronica."), ln=True)

    # Recopilar PDFs de los documentos de los pasos para anexarlos al final.
    pasos_docs_dir = _exp_dir(int(exp["id"])) / "pasos_docs"
    anexos: list[tuple[str, str, Path]] = []  # (paso, nombre, ruta)
    for i, p in enumerate(_normalizar_pasos(exp.get("pasos")), 1):
        for d in (p.get("documentos") or []):
            arch = d.get("archivo")
            if not arch:
                continue
            ruta = pasos_docs_dir / arch
            if ruta.is_file() and ruta.suffix.lower() == ".pdf":
                anexos.append((f"{i}. {p['nombre']}",
                               d.get("nombre_original") or arch, ruta))

    if not anexos:
        pdf.output(str(destino))
        return

    # Escribimos el resumen a un temporal y luego fusionamos con pypdf.
    import tempfile
    try:
        from pypdf import PdfReader, PdfWriter
    except ModuleNotFoundError:
        try:
            from PyPDF2 import PdfReader, PdfWriter  # type: ignore
        except ModuleNotFoundError:
            # Sin libreria de fusion: generamos solo el resumen.
            pdf.output(str(destino))
            return

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        resumen_path = Path(tmp.name)
    try:
        pdf.output(str(resumen_path))
        writer = PdfWriter()
        for page in PdfReader(str(resumen_path)).pages:
            writer.add_page(page)
        for paso, nombre, ruta in anexos:
            # Portadilla por documento adjunto.
            sep = FPDF()
            sep.set_auto_page_break(auto=True, margin=18)
            sep.add_page()
            sep.set_font("Helvetica", "B", 14)
            sep.multi_cell(0, 8, _l1(f"Paso: {paso}"),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            sep.set_font("Helvetica", "", 12)
            sep.multi_cell(0, 7, _l1(f"Documento: {nombre}"),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tsep:
                sep_path = Path(tsep.name)
            try:
                sep.output(str(sep_path))
                for page in PdfReader(str(sep_path)).pages:
                    writer.add_page(page)
            finally:
                sep_path.unlink(missing_ok=True)
            try:
                for page in PdfReader(str(ruta)).pages:
                    writer.add_page(page)
            except Exception:
                # Si un PDF esta corrupto o cifrado, lo saltamos sin abortar.
                continue
        with open(destino, "wb") as fh:
            writer.write(fh)
    finally:
        resumen_path.unlink(missing_ok=True)


# ===================================================== utilidades expedientes
def _exp_dir(id_: int) -> Path:
    d = EXP_DIR / str(id_)
    d.mkdir(parents=True, exist_ok=True)
    (d / "adjuntos").mkdir(exist_ok=True)
    return d


def _normalizar_pasos(pasos) -> list[dict]:
    """Convierte la lista de pasos al formato canonico {nombre, documentos:[]}.

    Acepta entradas en el formato antiguo (str) y nuevo (dict).
    """
    out: list[dict] = []
    for p in pasos or []:
        if isinstance(p, str):
            nombre = p.strip()
            docs = []
        elif isinstance(p, dict):
            nombre = str(p.get("nombre") or "").strip()
            docs = p.get("documentos") or []
            if not isinstance(docs, list):
                docs = []
        else:
            continue
        if not nombre:
            continue
        out.append({"nombre": nombre[:200], "documentos": docs})
    return out


def _exp_publico(exp: dict) -> dict:
    """Version del expediente con URLs y campos calculados."""
    eid = exp["id"]
    out = dict(exp)
    out["pdf_url"] = f"/api/expedientes/{eid}/pdf" if exp.get("pdf") else None
    out["firmado_url"] = f"/api/expedientes/{eid}/firmado" if exp.get("firmado") else None
    out["adjuntos"] = [
        {**a, "url": f"/api/expedientes/{eid}/adjuntos/{i}"}
        for i, a in enumerate(exp.get("adjuntos") or [])
    ]
    pasos_norm = _normalizar_pasos(exp.get("pasos"))
    out["pasos"] = [
        {
            "nombre": p["nombre"],
            "documentos": [
                {**d, "url": f"/api/expedientes/{eid}/pasos/{i}/documentos/{j}"}
                for j, d in enumerate(p.get("documentos") or [])
            ],
        }
        for i, p in enumerate(pasos_norm)
    ]
    return out


def _buscar_indice(items: list, id_: int) -> int:
    for i, e in enumerate(items):
        if int(e.get("id", -1)) == int(id_):
            return i
    return -1


def _ahora() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# ====================================================================== auth
@app.post("/api/registro")
def registro():
    body = request.get_json(silent=True) or {}
    usuario = (body.get("usuario") or "").strip().lower()
    password = body.get("password") or ""
    if not _validar_usuario(usuario):
        return jsonify({"error": "usuario invalido"}), 400
    if len(password) < 6:
        return jsonify({"error": "password minimo 6 caracteres"}), 400
    with _LOCK:
        data = _cargar_auth()
        if usuario in data.get("usuarios", {}):
            return jsonify({"error": "el usuario ya existe"}), 409
        data.setdefault("usuarios", {})[usuario] = {
            "bcrypt": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            "creado": _ahora(),
        }
        _guardar_auth(data)
    return jsonify({"ok": True})


@app.post("/api/login")
def login():
    body = request.get_json(silent=True) or {}
    usuario = (body.get("usuario") or "").strip().lower()
    password = body.get("password") or ""
    with _LOCK:
        data = _cargar_auth()
        info = data.get("usuarios", {}).get(usuario)
        if not info or not bcrypt.checkpw(password.encode(), info["bcrypt"].encode()):
            return jsonify({"error": "credenciales invalidas"}), 401
        token = secrets.token_urlsafe(32)
        data.setdefault("tokens", {})[token] = {
            "usuario": usuario,
            "exp": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }
        info["ultimo_acceso"] = _ahora()
        _purgar_tokens(data)
        _guardar_auth(data)
    resp = jsonify({"ok": True, "usuario": usuario})
    resp.set_cookie("sesion", token, max_age=7 * 24 * 3600,
                    httponly=True, samesite="Lax", path="/")
    return resp


@app.post("/api/logout")
def logout():
    token = request.cookies.get("sesion")
    if token:
        with _LOCK:
            data = _cargar_auth()
            data.get("tokens", {}).pop(token, None)
            _guardar_auth(data)
    resp = jsonify({"ok": True})
    resp.delete_cookie("sesion", path="/")
    return resp


@app.get("/api/me")
def me():
    usuario = _sesion_actual()
    if not usuario:
        return jsonify({"autenticado": False})
    return jsonify({"autenticado": True, "usuario": usuario})


# =============================================================== AutoFirma info
@app.get("/api/autofirma/estado")
def autofirma_estado():
    ruta = _localizar_autofirma()
    return jsonify({"instalado": bool(ruta), "ruta": ruta})


@app.get("/api/certificados")
def certificados():
    _, err = _requiere_login()
    if err:
        return err
    return jsonify({"items": _listar_certificados_windows(),
                    "soportado": os.name == "nt"})


# ============================================================= catalogo pasos
@app.get("/api/pasos")
def listar_pasos():
    return jsonify({"items": PASOS_ADMINISTRATIVOS})


# ============================================================== expedientes
@app.get("/api/expedientes")
def listar_expedientes():
    usuario, err = _requiere_login()
    if err:
        return err
    q = (request.args.get("q") or "").strip().lower()
    id_buscado = (request.args.get("id") or "").strip()

    with _LOCK:
        data = _cargar_exp()

    items = data.get("items", [])
    # Filtro por usuario
    items = [e for e in items if e.get("usuario") == usuario]

    if id_buscado:
        try:
            n = int(id_buscado)
            items = [e for e in items if int(e["id"]) == n]
        except ValueError:
            items = [e for e in items if id_buscado in str(e["id"])]
    if q:
        items = [e for e in items if q in (e.get("referencia") or "").lower()]

    items = sorted(items, key=lambda e: e["id"], reverse=True)
    return jsonify({"items": [_exp_publico(e) for e in items]})


@app.post("/api/expedientes")
def crear_expediente():
    usuario, err = _requiere_login()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    referencia = (body.get("referencia") or "").strip()
    descripcion = (body.get("descripcion") or "").strip()
    pasos = _normalizar_pasos(body.get("pasos") or [])

    if not referencia:
        return jsonify({"error": "la referencia es obligatoria"}), 400

    with _LOCK:
        data = _cargar_exp()
        data["contador"] = int(data.get("contador", 0)) + 1
        nuevo_id = data["contador"]
        ahora = _ahora()
        exp = {
            "id": nuevo_id,
            "usuario": usuario,
            "referencia": referencia[:200],
            "descripcion": descripcion[:5000],
            "pasos": pasos,
            "adjuntos": [],
            "estado": ESTADO_BORRADOR,
            "pdf": None,
            "firmado": None,
            "fecha_creacion": ahora,
            "fecha_modificacion": ahora,
        }
        data.setdefault("items", []).append(exp)
        _guardar_exp(data)
        _exp_dir(nuevo_id)
    return jsonify(_exp_publico(exp)), 201


def _obtener_y_validar(id_: int, usuario: str, escribir: bool = False):
    """Devuelve (data, idx, exp, error_response)."""
    with _LOCK:
        data = _cargar_exp()
        idx = _buscar_indice(data.get("items", []), id_)
        if idx < 0:
            return None, -1, None, (jsonify({"error": "expediente no encontrado"}), 404)
        exp = data["items"][idx]
        if exp.get("usuario") != usuario:
            return None, -1, None, (jsonify({"error": "expediente no encontrado"}), 404)
    return data, idx, exp, None


@app.get("/api/expedientes/<int:id_>")
def obtener_expediente(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    _, _, exp, e = _obtener_y_validar(id_, usuario)
    if e:
        return e
    return jsonify(_exp_publico(exp))


@app.put("/api/expedientes/<int:id_>")
def editar_expediente(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    with _LOCK:
        data = _cargar_exp()
        idx = _buscar_indice(data.get("items", []), id_)
        if idx < 0 or data["items"][idx].get("usuario") != usuario:
            return jsonify({"error": "expediente no encontrado"}), 404
        exp = data["items"][idx]
        if exp.get("estado") == ESTADO_FIRMADO:
            return jsonify({"error": "no se puede editar un expediente firmado"}), 409

        if "referencia" in body:
            ref = (body.get("referencia") or "").strip()
            if not ref:
                return jsonify({"error": "la referencia es obligatoria"}), 400
            exp["referencia"] = ref[:200]
        if "descripcion" in body:
            exp["descripcion"] = (body.get("descripcion") or "").strip()[:5000]
        if "pasos" in body:
            pasos_in = body.get("pasos") or []
            if not isinstance(pasos_in, list):
                return jsonify({"error": "pasos debe ser lista"}), 400
            # Conservamos los documentos del paso existente cuando el cliente
            # envia solo strings (lista de nombres seleccionados).
            existentes = {p["nombre"]: p.get("documentos", [])
                          for p in _normalizar_pasos(exp.get("pasos"))}
            nuevos = []
            usados_archivos: set[str] = set()
            for p in pasos_in:
                if isinstance(p, str):
                    nombre = p.strip()
                    docs = existentes.get(nombre, [])
                elif isinstance(p, dict):
                    nombre = str(p.get("nombre") or "").strip()
                    docs = p.get("documentos") or existentes.get(nombre, [])
                else:
                    continue
                if not nombre:
                    continue
                nuevos.append({"nombre": nombre[:200], "documentos": docs})
                for d in docs:
                    if d.get("archivo"):
                        usados_archivos.add(d["archivo"])
            # Borrar archivos de pasos eliminados
            dir_pasos = _exp_dir(id_) / "pasos_docs"
            if dir_pasos.is_dir():
                for f in dir_pasos.iterdir():
                    if f.is_file() and f.name not in usados_archivos:
                        try:
                            f.unlink()
                        except Exception:
                            pass
            exp["pasos"] = nuevos

        # Si se modifica, el PDF generado deja de ser valido
        if exp.get("estado") == ESTADO_PDF:
            exp["estado"] = ESTADO_BORRADOR
            try:
                if exp.get("pdf"):
                    (_exp_dir(id_) / exp["pdf"]).unlink(missing_ok=True)
            except Exception:
                pass
            exp["pdf"] = None

        exp["fecha_modificacion"] = _ahora()
        data["items"][idx] = exp
        _guardar_exp(data)
    return jsonify(_exp_publico(exp))


@app.delete("/api/expedientes/<int:id_>")
def borrar_expediente(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    with _LOCK:
        data = _cargar_exp()
        idx = _buscar_indice(data.get("items", []), id_)
        if idx < 0 or data["items"][idx].get("usuario") != usuario:
            return jsonify({"error": "expediente no encontrado"}), 404
        exp = data["items"][idx]
        if exp.get("estado") == ESTADO_FIRMADO:
            return jsonify({
                "error": "no se puede borrar un expediente firmado",
            }), 409
        # borrar archivos
        try:
            d = _exp_dir(id_)
            shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass
        data["items"].pop(idx)
        _guardar_exp(data)
    return jsonify({"ok": True})


# =================================================== documentos por paso
def _guardar_archivo_pdf_o_docx(f, dir_destino: Path, base: str) -> tuple[Path, str, str | None]:
    """Guarda f en dir_destino. Si es DOCX lo convierte a PDF.

    Devuelve (pdf_path, ext_original, error_msg). Si error_msg es None, ok.
    """
    nombre = (f.filename or "").strip()
    ext = Path(nombre).suffix.lower()
    if ext not in (".pdf", ".docx"):
        return Path(), ext, "solo se aceptan PDF o DOCX"
    sufijo = secrets.token_hex(3)
    if ext == ".docx":
        docx_path = dir_destino / f"{base}_{sufijo}.docx"
        f.save(str(docx_path))
        pdf_path = dir_destino / f"{base}_{sufijo}.pdf"
        ok, msg = _docx_a_pdf(docx_path, pdf_path)
        try:
            docx_path.unlink(missing_ok=True)
        except Exception:
            pass
        if not ok:
            return Path(), ext, msg
        return pdf_path, ext, None
    pdf_path = dir_destino / f"{base}_{sufijo}.pdf"
    f.save(str(pdf_path))
    return pdf_path, ext, None


@app.post("/api/expedientes/<int:id_>/pasos/<int:idx>/documentos")
def subir_doc_paso(id_: int, idx: int):
    usuario, err = _requiere_login()
    if err:
        return err
    if "archivo" not in request.files:
        return jsonify({"error": "falta el campo 'archivo'"}), 400
    f = request.files["archivo"]
    nombre = (f.filename or "").strip()
    if not nombre:
        return jsonify({"error": "archivo sin nombre"}), 400

    _, _, exp, e = _obtener_y_validar(id_, usuario)
    if e:
        return e
    if exp.get("estado") == ESTADO_FIRMADO:
        return jsonify({"error": "expediente firmado, no se puede modificar"}), 409

    pasos = _normalizar_pasos(exp.get("pasos"))
    if not (0 <= idx < len(pasos)):
        return jsonify({"error": "paso no encontrado"}), 404

    seguro = "".join(c for c in nombre if c.isalnum() or c in "._- ").strip().replace(" ", "_") or "documento"
    base = Path(seguro).stem[:60]
    dir_pasos = _exp_dir(id_) / "pasos_docs"
    dir_pasos.mkdir(parents=True, exist_ok=True)

    pdf_path, _, msg = _guardar_archivo_pdf_o_docx(f, dir_pasos, base)
    if msg:
        return jsonify({"error": msg}), 502

    with _LOCK:
        data = _cargar_exp()
        i_exp = _buscar_indice(data.get("items", []), id_)
        exp = data["items"][i_exp]
        pasos_act = _normalizar_pasos(exp.get("pasos"))
        if not (0 <= idx < len(pasos_act)):
            return jsonify({"error": "paso no encontrado"}), 404
        doc = {
            "archivo": pdf_path.name,
            "nombre_original": nombre,
            "tamano": pdf_path.stat().st_size,
            "subido": _ahora(),
        }
        pasos_act[idx]["documentos"] = list(pasos_act[idx].get("documentos") or []) + [doc]
        exp["pasos"] = pasos_act
        if exp.get("estado") == ESTADO_PDF:
            exp["estado"] = ESTADO_BORRADOR
            try:
                if exp.get("pdf"):
                    (_exp_dir(id_) / exp["pdf"]).unlink(missing_ok=True)
            except Exception:
                pass
            exp["pdf"] = None
        exp["fecha_modificacion"] = _ahora()
        data["items"][i_exp] = exp
        _guardar_exp(data)
    return jsonify(_exp_publico(exp))


@app.delete("/api/expedientes/<int:id_>/pasos/<int:idx>/documentos/<int:didx>")
def borrar_doc_paso(id_: int, idx: int, didx: int):
    usuario, err = _requiere_login()
    if err:
        return err
    with _LOCK:
        data = _cargar_exp()
        i_exp = _buscar_indice(data.get("items", []), id_)
        if i_exp < 0 or data["items"][i_exp].get("usuario") != usuario:
            return jsonify({"error": "expediente no encontrado"}), 404
        exp = data["items"][i_exp]
        if exp.get("estado") == ESTADO_FIRMADO:
            return jsonify({"error": "expediente firmado, no se puede modificar"}), 409
        pasos = _normalizar_pasos(exp.get("pasos"))
        if not (0 <= idx < len(pasos)):
            return jsonify({"error": "paso no encontrado"}), 404
        docs = list(pasos[idx].get("documentos") or [])
        if not (0 <= didx < len(docs)):
            return jsonify({"error": "documento no encontrado"}), 404
        d = docs.pop(didx)
        try:
            (_exp_dir(id_) / "pasos_docs" / d["archivo"]).unlink(missing_ok=True)
        except Exception:
            pass
        pasos[idx]["documentos"] = docs
        exp["pasos"] = pasos
        if exp.get("estado") == ESTADO_PDF:
            exp["estado"] = ESTADO_BORRADOR
            try:
                if exp.get("pdf"):
                    (_exp_dir(id_) / exp["pdf"]).unlink(missing_ok=True)
            except Exception:
                pass
            exp["pdf"] = None
        exp["fecha_modificacion"] = _ahora()
        data["items"][i_exp] = exp
        _guardar_exp(data)
    return jsonify(_exp_publico(exp))


@app.get("/api/expedientes/<int:id_>/pasos/<int:idx>/documentos/<int:didx>")
def descargar_doc_paso(id_: int, idx: int, didx: int):
    usuario, err = _requiere_login()
    if err:
        return err
    _, _, exp, e = _obtener_y_validar(id_, usuario)
    if e:
        return e
    pasos = _normalizar_pasos(exp.get("pasos"))
    if not (0 <= idx < len(pasos)):
        return jsonify({"error": "paso no encontrado"}), 404
    docs = pasos[idx].get("documentos") or []
    if not (0 <= didx < len(docs)):
        return jsonify({"error": "documento no encontrado"}), 404
    d = docs[didx]
    ruta = _exp_dir(id_) / "pasos_docs" / d["archivo"]
    if not ruta.is_file():
        return jsonify({"error": "no encontrado"}), 404
    return send_file(str(ruta), mimetype="application/pdf",
                     as_attachment=False,
                     download_name=d.get("nombre_original") or d["archivo"])


# ============================================================== adjuntos
@app.post("/api/expedientes/<int:id_>/adjuntos")
def subir_adjunto(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    if "archivo" not in request.files:
        return jsonify({"error": "falta el campo 'archivo'"}), 400
    f = request.files["archivo"]
    nombre = (f.filename or "").strip()
    if not nombre:
        return jsonify({"error": "archivo sin nombre"}), 400

    ext = Path(nombre).suffix.lower()
    if ext not in (".pdf", ".docx"):
        return jsonify({"error": "solo se aceptan PDF o DOCX"}), 400

    _, _, exp, e = _obtener_y_validar(id_, usuario)
    if e:
        return e
    if exp.get("estado") == ESTADO_FIRMADO:
        return jsonify({"error": "expediente firmado, no se pueden anadir adjuntos"}), 409

    seguro = "".join(c for c in nombre if c.isalnum() or c in "._- ").strip().replace(" ", "_") or "archivo"
    base = Path(seguro).stem[:60]
    sufijo = secrets.token_hex(3)
    dir_adj = _exp_dir(id_) / "adjuntos"

    if ext == ".docx":
        docx_path = dir_adj / f"{base}_{sufijo}.docx"
        f.save(str(docx_path))
        pdf_path = dir_adj / f"{base}_{sufijo}.pdf"
        ok, msg = _docx_a_pdf(docx_path, pdf_path)
        try:
            docx_path.unlink(missing_ok=True)
        except Exception:
            pass
        if not ok:
            return jsonify({"error": msg}), 502
        nombre_archivo = pdf_path.name
        nombre_original = nombre
    else:
        pdf_path = dir_adj / f"{base}_{sufijo}.pdf"
        f.save(str(pdf_path))
        nombre_archivo = pdf_path.name
        nombre_original = nombre

    with _LOCK:
        data = _cargar_exp()
        idx = _buscar_indice(data.get("items", []), id_)
        exp = data["items"][idx]
        adj = {
            "archivo": nombre_archivo,
            "nombre_original": nombre_original,
            "tamano": pdf_path.stat().st_size,
            "subido": _ahora(),
        }
        exp.setdefault("adjuntos", []).append(adj)
        # invalidar PDF resumen si ya existia
        if exp.get("estado") == ESTADO_PDF:
            exp["estado"] = ESTADO_BORRADOR
            try:
                (_exp_dir(id_) / exp.get("pdf", "")).unlink(missing_ok=True)
            except Exception:
                pass
            exp["pdf"] = None
        exp["fecha_modificacion"] = _ahora()
        data["items"][idx] = exp
        _guardar_exp(data)
    return jsonify(_exp_publico(exp))


@app.delete("/api/expedientes/<int:id_>/adjuntos/<int:n>")
def borrar_adjunto(id_: int, n: int):
    usuario, err = _requiere_login()
    if err:
        return err
    with _LOCK:
        data = _cargar_exp()
        idx = _buscar_indice(data.get("items", []), id_)
        if idx < 0 or data["items"][idx].get("usuario") != usuario:
            return jsonify({"error": "expediente no encontrado"}), 404
        exp = data["items"][idx]
        if exp.get("estado") == ESTADO_FIRMADO:
            return jsonify({"error": "expediente firmado, no se puede modificar"}), 409
        adjs = exp.get("adjuntos") or []
        if not (0 <= n < len(adjs)):
            return jsonify({"error": "adjunto no encontrado"}), 404
        adj = adjs.pop(n)
        try:
            (_exp_dir(id_) / "adjuntos" / adj["archivo"]).unlink(missing_ok=True)
        except Exception:
            pass
        if exp.get("estado") == ESTADO_PDF:
            exp["estado"] = ESTADO_BORRADOR
            try:
                (_exp_dir(id_) / exp.get("pdf", "")).unlink(missing_ok=True)
            except Exception:
                pass
            exp["pdf"] = None
        exp["fecha_modificacion"] = _ahora()
        data["items"][idx] = exp
        _guardar_exp(data)
    return jsonify(_exp_publico(exp))


@app.get("/api/expedientes/<int:id_>/adjuntos/<int:n>")
def descargar_adjunto(id_: int, n: int):
    usuario, err = _requiere_login()
    if err:
        return err
    _, _, exp, e = _obtener_y_validar(id_, usuario)
    if e:
        return e
    adjs = exp.get("adjuntos") or []
    if not (0 <= n < len(adjs)):
        return jsonify({"error": "adjunto no encontrado"}), 404
    adj = adjs[n]
    ruta = _exp_dir(id_) / "adjuntos" / adj["archivo"]
    if not ruta.is_file():
        return jsonify({"error": "no encontrado"}), 404
    return send_file(str(ruta), mimetype="application/pdf",
                     as_attachment=False, download_name=adj.get("nombre_original") or adj["archivo"])


# =================================================== generar / firmar PDF
@app.post("/api/expedientes/<int:id_>/generar")
def generar_pdf(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    with _LOCK:
        data = _cargar_exp()
        idx = _buscar_indice(data.get("items", []), id_)
        if idx < 0 or data["items"][idx].get("usuario") != usuario:
            return jsonify({"error": "expediente no encontrado"}), 404
        exp = data["items"][idx]
        if exp.get("estado") == ESTADO_FIRMADO:
            return jsonify({"error": "expediente ya firmado"}), 409
        try:
            destino = _exp_dir(id_) / f"expediente_{id_}.pdf"
            _generar_pdf_expediente(exp, destino)
        except Exception as e:
            return jsonify({"error": f"no se pudo generar el PDF: {e}"}), 500
        exp["pdf"] = destino.name
        exp["estado"] = ESTADO_PDF
        exp["fecha_modificacion"] = _ahora()
        data["items"][idx] = exp
        _guardar_exp(data)
    return jsonify(_exp_publico(exp))


@app.get("/api/expedientes/<int:id_>/pdf")
def descargar_pdf(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    _, _, exp, e = _obtener_y_validar(id_, usuario)
    if e:
        return e
    if not exp.get("pdf"):
        return jsonify({"error": "PDF no generado"}), 404
    ruta = _exp_dir(id_) / exp["pdf"]
    if not ruta.is_file():
        return jsonify({"error": "PDF no encontrado en disco"}), 404
    return send_file(str(ruta), mimetype="application/pdf",
                     as_attachment=False, download_name=exp["pdf"])


@app.post("/api/expedientes/<int:id_>/firmar")
def firmar_expediente(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    thumb = (body.get("thumbprint") or "").strip()

    with _LOCK:
        data = _cargar_exp()
        idx = _buscar_indice(data.get("items", []), id_)
        if idx < 0 or data["items"][idx].get("usuario") != usuario:
            return jsonify({"error": "expediente no encontrado"}), 404
        exp = data["items"][idx]
        if exp.get("estado") == ESTADO_FIRMADO:
            return jsonify({"error": "expediente ya firmado"}), 409
        if not exp.get("pdf"):
            return jsonify({"error": "primero hay que generar el PDF"}), 400

    if not _localizar_autofirma():
        return jsonify({
            "error": "AutoFirma no esta instalado",
            "detalle": "Descarguelo desde firmaelectronica.gob.es",
        }), 503

    pdf_in = _exp_dir(id_) / exp["pdf"]
    pdf_out = _exp_dir(id_) / f"expediente_{id_}_firmado.pdf"
    ok, msg = _firmar_pdf(pdf_in, pdf_out, thumbprint=thumb)
    if not ok:
        return jsonify({"error": msg}), 502

    with _LOCK:
        data = _cargar_exp()
        idx = _buscar_indice(data.get("items", []), id_)
        exp = data["items"][idx]
        exp["firmado"] = pdf_out.name
        exp["estado"] = ESTADO_FIRMADO
        exp["fecha_firma"] = _ahora()
        exp["fecha_modificacion"] = exp["fecha_firma"]
        data["items"][idx] = exp
        _guardar_exp(data)
    return jsonify(_exp_publico(exp))


@app.get("/api/expedientes/<int:id_>/firmado")
def descargar_firmado(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    _, _, exp, e = _obtener_y_validar(id_, usuario)
    if e:
        return e
    if not exp.get("firmado"):
        return jsonify({"error": "expediente no firmado"}), 404
    ruta = _exp_dir(id_) / exp["firmado"]
    if not ruta.is_file():
        return jsonify({"error": "PDF firmado no encontrado en disco"}), 404
    return send_file(str(ruta), mimetype="application/pdf",
                     as_attachment=False, download_name=exp["firmado"])


# ============================================================ DOCUMENTOS
@app.get("/api/documentos")
def listar_documentos():
    usuario, err = _requiere_login()
    if err:
        return err
    with _LOCK:
        data = _cargar_doc()
    items = [d for d in data.get("items", []) if d.get("usuario") == usuario]
    items = sorted(items, key=lambda d: d["id"], reverse=True)
    return jsonify({"items": [_doc_publico(d) for d in items]})


@app.post("/api/documentos")
def subir_documento():
    usuario, err = _requiere_login()
    if err:
        return err
    if "archivo" not in request.files:
        return jsonify({"error": "falta el campo 'archivo'"}), 400
    f = request.files["archivo"]
    nombre = (f.filename or "").strip()
    if not nombre:
        return jsonify({"error": "archivo sin nombre"}), 400
    ext = Path(nombre).suffix.lower()
    if ext not in (".pdf", ".docx"):
        return jsonify({"error": "solo se aceptan PDF o DOCX"}), 400

    with _LOCK:
        data = _cargar_doc()
        data["contador"] = int(data.get("contador", 0)) + 1
        nuevo_id = data["contador"]

    d = _doc_dir(nuevo_id)
    seguro = "".join(c for c in nombre if c.isalnum() or c in "._- ").strip().replace(" ", "_") or "documento"
    base = Path(seguro).stem[:60]

    if ext == ".docx":
        docx_path = d / f"{base}.docx"
        f.save(str(docx_path))
        pdf_path = d / f"{base}.pdf"
        ok, msg = _docx_a_pdf(docx_path, pdf_path)
        try:
            docx_path.unlink(missing_ok=True)
        except Exception:
            pass
        if not ok:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
            with _LOCK:
                data2 = _cargar_doc()
                data2["contador"] = max(0, int(data2.get("contador", 0)) - 1)
                _guardar_doc(data2)
            return jsonify({"error": msg}), 502
    else:
        pdf_path = d / f"{base}.pdf"
        f.save(str(pdf_path))

    doc = {
        "id": nuevo_id,
        "usuario": usuario,
        "nombre_original": nombre,
        "pdf": pdf_path.name,
        "firmado": None,
        "estado": ESTADO_PDF,
        "tamano": pdf_path.stat().st_size,
        "fecha_subida": _ahora(),
    }
    with _LOCK:
        data = _cargar_doc()
        # Sincronizar contador (por si hubo varias subidas concurrentes)
        if int(data.get("contador", 0)) < nuevo_id:
            data["contador"] = nuevo_id
        data.setdefault("items", []).append(doc)
        _guardar_doc(data)
    return jsonify(_doc_publico(doc)), 201


def _obtener_doc(id_: int, usuario: str):
    with _LOCK:
        data = _cargar_doc()
        idx = _buscar_indice(data.get("items", []), id_)
        if idx < 0:
            return None, -1, None, (jsonify({"error": "documento no encontrado"}), 404)
        doc = data["items"][idx]
        if doc.get("usuario") != usuario:
            return None, -1, None, (jsonify({"error": "documento no encontrado"}), 404)
    return data, idx, doc, None


@app.get("/api/documentos/<int:id_>")
def obtener_documento(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    _, _, doc, e = _obtener_doc(id_, usuario)
    if e:
        return e
    return jsonify(_doc_publico(doc))


@app.delete("/api/documentos/<int:id_>")
def borrar_documento(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    with _LOCK:
        data = _cargar_doc()
        idx = _buscar_indice(data.get("items", []), id_)
        if idx < 0 or data["items"][idx].get("usuario") != usuario:
            return jsonify({"error": "documento no encontrado"}), 404
        doc = data["items"][idx]
        if doc.get("estado") == ESTADO_FIRMADO:
            return jsonify({"error": "no se puede borrar un documento firmado"}), 409
        try:
            shutil.rmtree(_doc_dir(id_), ignore_errors=True)
        except Exception:
            pass
        data["items"].pop(idx)
        _guardar_doc(data)
    return jsonify({"ok": True})


@app.get("/api/documentos/<int:id_>/pdf")
def descargar_documento(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    _, _, doc, e = _obtener_doc(id_, usuario)
    if e:
        return e
    if not doc.get("pdf"):
        return jsonify({"error": "PDF no encontrado"}), 404
    ruta = _doc_dir(id_) / doc["pdf"]
    if not ruta.is_file():
        return jsonify({"error": "PDF no encontrado en disco"}), 404
    return send_file(str(ruta), mimetype="application/pdf",
                     as_attachment=False, download_name=doc["pdf"])


@app.post("/api/documentos/<int:id_>/firmar")
def firmar_documento(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    thumb = (body.get("thumbprint") or "").strip()

    _, _, doc, e = _obtener_doc(id_, usuario)
    if e:
        return e
    if doc.get("estado") == ESTADO_FIRMADO:
        return jsonify({"error": "documento ya firmado"}), 409
    if not _localizar_autofirma():
        return jsonify({
            "error": "AutoFirma no esta instalado",
            "detalle": "Descarguelo desde firmaelectronica.gob.es",
        }), 503

    pdf_in = _doc_dir(id_) / doc["pdf"]
    if not pdf_in.is_file():
        return jsonify({"error": "PDF original no encontrado"}), 404
    pdf_out = _doc_dir(id_) / (Path(doc["pdf"]).stem + "_firmado.pdf")
    ok, msg = _firmar_pdf(pdf_in, pdf_out, thumbprint=thumb)
    if not ok:
        return jsonify({"error": msg}), 502

    with _LOCK:
        data = _cargar_doc()
        idx = _buscar_indice(data.get("items", []), id_)
        d = data["items"][idx]
        d["firmado"] = pdf_out.name
        d["estado"] = ESTADO_FIRMADO
        d["fecha_firma"] = _ahora()
        data["items"][idx] = d
        _guardar_doc(data)
    return jsonify(_doc_publico(d))


@app.get("/api/documentos/<int:id_>/firmado")
def descargar_doc_firmado(id_: int):
    usuario, err = _requiere_login()
    if err:
        return err
    _, _, doc, e = _obtener_doc(id_, usuario)
    if e:
        return e
    if not doc.get("firmado"):
        return jsonify({"error": "documento no firmado"}), 404
    ruta = _doc_dir(id_) / doc["firmado"]
    if not ruta.is_file():
        return jsonify({"error": "PDF firmado no encontrado en disco"}), 404
    return send_file(str(ruta), mimetype="application/pdf",
                     as_attachment=False, download_name=doc["firmado"])


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
