"""Prueba de integracion: una sola llamada real a la API de SECOP II.

Se ejecuta aparte con `pytest -m integracion` para no saturar la API publica.
"""

import pytest
import requests

from src.fase2_secop_tools import buscar_proveedores_secop


@pytest.mark.integracion
def test_buscar_proveedores_api_real():
    try:
        resultado = buscar_proveedores_secop("software", "Bogotá DC")
    except requests.RequestException as e:
        pytest.skip(f"API de SECOP II no disponible: {e}")

    assert isinstance(resultado, str)
    assert "software" in resultado
    assert "Proveedor" in resultado or "No se encontraron" in resultado