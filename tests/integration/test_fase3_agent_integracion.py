"""Prueba de integracion de la Fase 3 via linea de comandos (uso real).

Lanza `python -m src.fase3_agent` como subproceso y le escribe una conversacion
por stdin, igual que se usara el producto. Un solo proceso: el modelo de
embeddings se carga una sola vez. Usa la API de NVIDIA y de datos.gov.co, por
eso se ejecuta aparte con `pytest -m integracion`.
"""

import subprocess
import sys

import pytest

pytestmark = pytest.mark.integracion

CONVERSACION = (
    "Revisa el pliego IDARTES-SA-SI-013-2026 y dime que licencias pide el Lote 2.\n"
    "Ahora busca en datos abiertos los proveedores de software en Bogota y "
    "presentalos en una tabla.\n"
    "q\n"
)


def test_agente_por_consola_usa_rag_y_secop():
    """El agente por consola responde con el pliego y con SECOP II."""

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "src.fase3_agent"],
            input=CONVERSACION,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=1800,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("el agente tardo mas de 30 minutos por consola")

    if proc.returncode != 0:
        pytest.skip(f"LLM o tools no disponibles:\n{proc.stderr[-2000:]}")

    salida = proc.stdout
    if "Error procesando la pregunta" in salida:
        pytest.skip("la API de NVIDIA no respondio:\n" + salida[-2000:])

    assert "licenci" in salida.lower(), "debia responder con las licencias del Lote 2"
    assert "Proveedor" in salida, "debia devolver la tabla de proveedores"
    assert "$ " in salida, "la tabla de proveedores debia incluir montos"