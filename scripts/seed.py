"""Trabajo Fin de Grado en Ingenieria Informatica
Universidad Internacional de La Rioja (UNIR)
Prototipo de software de tramitacion de expedientes electronicos para administraciones locales
Autor: Carlos Galvez Reguera
Ano: 2026

Este archivo forma parte de este proyecto, desarrollado como
Trabajo Fin de Grado en Ingenieria Informatica de la UNIR.

Licencia: MIT

Carga una bateria de expedientes de prueba.

Crea (si no existe) un usuario `test` con contrasena `test1234` y le asigna
una serie de expedientes con estados y datos variados, generando los PDFs
correspondientes con fpdf2 cuando aplica.

Uso (con el servidor parado o en marcha, da igual):
    python scripts/seed.py
"""
from __future__ import annotations

import os
import random
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
os.environ.setdefault("FIRMA_ROOT", str(ROOT))

import bcrypt  # noqa: E402

# Importamos el modulo del API para reutilizar helpers
from app import (  # noqa: E402
    DATA_DIR, EXP_DIR,
    _cargar_auth, _guardar_auth,
    _cargar_exp, _guardar_exp,
    _exp_dir, _generar_pdf_expediente,
    ESTADO_BORRADOR, ESTADO_PDF, ESTADO_FIRMADO,
    PASOS_ADMINISTRATIVOS,
)

USUARIO = "test"
PASSWORD = "test1234"

# Datos variados (referencia, descripcion, num_pasos, estado_objetivo)
PLANTILLAS = [
    ("Solicitud de licencia de obra menor en c/Mayor 12",
     "Reforma integral de cocina y bano, sin afectar a estructura. "
     "Adjunta presupuesto del contratista y memoria tecnica.",
     2, ESTADO_BORRADOR),

    ("Contratacion del servicio de limpieza viaria 2026",
     "Procedimiento abierto, plurianual, division en 3 lotes geograficos. "
     "Pliego de prescripciones tecnicas pendiente de informe juridico.",
     5, ESTADO_PDF),

    ("Subvencion para promocion turistica - convocatoria 2026",
     "Concesion en regimen de concurrencia competitiva, dotacion 80.000 EUR.",
     4, ESTADO_PDF),

    ("Recurso de reposicion contra liquidacion IBI 2025",
     "Interpuesto por el interesado fuera de plazo. Pendiente analizar admisibilidad.",
     3, ESTADO_BORRADOR),

    ("Aprobacion del Plan Especial de Proteccion del Casco Historico",
     "Tramite ambiental, audiencia publica y consulta a colegios profesionales.",
     7, ESTADO_FIRMADO),

    ("Expediente disciplinario a personal funcionario - falta leve",
     "Por incumplimiento de horario reiterado. Pliego de cargos en redaccion.",
     2, ESTADO_BORRADOR),

    ("Convenio de colaboracion con Diputacion - vias rurales",
     "Cofinanciacion 60/40, mantenimiento de caminos rurales del termino municipal.",
     4, ESTADO_PDF),

    ("Compra de material informatico ejercicio 2026 - lote A",
     "Adquisicion de 25 equipos para puestos administrativos. Contrato menor.",
     3, ESTADO_FIRMADO),

    ("Solicitud de vado permanente en c/Andalucia 27",
     "Vivienda unifamiliar con cochera. Informe favorable de la policia local.",
     2, ESTADO_BORRADOR),

    ("Modificacion de credito - transferencia entre aplicaciones",
     "Suplemento por mayor gasto en suministro electrico. Informe de Intervencion.",
     3, ESTADO_PDF),

    ("Bases de la convocatoria de empleo publico - tecnico de gestion",
     "Una plaza, sistema de oposicion libre. Publicacion en BOP pendiente.",
     5, ESTADO_PDF),

    ("Resolucion de baja de oficio en padron municipal",
     "Vivienda deshabitada confirmada por la policia local tras dos visitas.",
     4, ESTADO_FIRMADO),

    ("Licitacion del suministro de gas natural 2026-2028",
     "Procedimiento abierto simplificado, valor estimado 145.000 EUR.",
     6, ESTADO_PDF),

    ("Reclamacion patrimonial por caida en via publica",
     "Acaecida el 12/03/2026 en c/del Parque. Adjunta parte medico y testigos.",
     3, ESTADO_BORRADOR),

    ("Aprobacion de la cuenta general del ejercicio 2025",
     "Dictaminada favorablemente por la Comision Especial de Cuentas.",
     5, ESTADO_FIRMADO),
]


def _ahora_iso(delta_dias: int = 0) -> str:
    return (datetime.utcnow() - timedelta(days=delta_dias)).isoformat(timespec="seconds")


def _asegurar_usuario() -> None:
    auth = _cargar_auth()
    if USUARIO not in auth.get("usuarios", {}):
        auth.setdefault("usuarios", {})[USUARIO] = {
            "bcrypt": bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode(),
            "creado": _ahora_iso(),
        }
        _guardar_auth(auth)
        print(f"  Usuario '{USUARIO}' creado (password: {PASSWORD})")
    else:
        print(f"  Usuario '{USUARIO}' ya existia, mantenido.")


def _limpiar_anteriores() -> None:
    """Borra expedientes previos del usuario test (no toca otros usuarios)."""
    data = _cargar_exp()
    items = data.get("items", [])
    a_borrar = [e for e in items if e.get("usuario") == USUARIO]
    if not a_borrar:
        return
    print(f"  Limpiando {len(a_borrar)} expedientes previos de '{USUARIO}'...")
    for e in a_borrar:
        try:
            shutil.rmtree(EXP_DIR / str(e["id"]), ignore_errors=True)
        except Exception:
            pass
    data["items"] = [e for e in items if e.get("usuario") != USUARIO]
    _guardar_exp(data)


def _crear_expediente(plantilla: tuple[str, str, int, str], antiguedad_dias: int) -> None:
    referencia, descripcion, n_pasos, estado_obj = plantilla
    nombres = PASOS_ADMINISTRATIVOS[: max(1, min(n_pasos, len(PASOS_ADMINISTRATIVOS)))]
    pasos = [{"nombre": n, "documentos": []} for n in nombres]

    data = _cargar_exp()
    data["contador"] = int(data.get("contador", 0)) + 1
    nuevo_id = data["contador"]
    fecha_creacion = _ahora_iso(antiguedad_dias)
    fecha_mod = _ahora_iso(max(0, antiguedad_dias - random.randint(0, antiguedad_dias)))
    exp = {
        "id": nuevo_id,
        "usuario": USUARIO,
        "referencia": referencia,
        "descripcion": descripcion,
        "pasos": pasos,
        "adjuntos": [],
        "estado": ESTADO_BORRADOR,
        "pdf": None,
        "firmado": None,
        "fecha_creacion": fecha_creacion,
        "fecha_modificacion": fecha_mod,
    }

    # Generar PDF resumen y, si toca, "firmar" (en seed se copia como firmado).
    if estado_obj in (ESTADO_PDF, ESTADO_FIRMADO):
        d = _exp_dir(nuevo_id)
        pdf_resumen = d / f"expediente_{nuevo_id}.pdf"
        try:
            _generar_pdf_expediente(exp, pdf_resumen)
            exp["pdf"] = pdf_resumen.name
            exp["estado"] = ESTADO_PDF
        except Exception as e:
            print(f"  ! no se pudo generar PDF de #{nuevo_id}: {e}")

        if estado_obj == ESTADO_FIRMADO and exp.get("pdf"):
            firmado = d / f"expediente_{nuevo_id}_firmado.pdf"
            shutil.copyfile(pdf_resumen, firmado)
            exp["firmado"] = firmado.name
            exp["estado"] = ESTADO_FIRMADO
            exp["fecha_firma"] = fecha_mod

    data.setdefault("items", []).append(exp)
    _guardar_exp(data)
    print(f"  #{nuevo_id:3d} [{exp['estado']:>13}] {referencia[:60]}")


def main() -> None:
    print("=" * 70)
    print("  Seed de expedientes de prueba")
    print("=" * 70)
    _asegurar_usuario()
    _limpiar_anteriores()

    random.seed(42)
    plantillas = list(PLANTILLAS)
    random.shuffle(plantillas)
    for i, p in enumerate(plantillas):
        _crear_expediente(p, antiguedad_dias=random.randint(0, 30))

    data = _cargar_exp()
    total = sum(1 for e in data.get("items", []) if e.get("usuario") == USUARIO)
    print()
    print(f"  Listo. {total} expedientes para usuario '{USUARIO}' (pwd: {PASSWORD}).")
    print("=" * 70)


if __name__ == "__main__":
    main()
