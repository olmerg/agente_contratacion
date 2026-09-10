from pathlib import Path

import pandas as pd

from src.fase2_secop_tools import buscar_proveedores_secop

FIXTURE = Path(__file__).parent / "data" / "secop_consulta_software.csv"


def _filas_fixture() -> list[dict]:
    """Las filas reales descargadas una sola vez (para no llamar a la API)."""
    return pd.read_csv(FIXTURE).to_dict("records")


def _cliente_fake(filas: list[dict]):
    """Crea un Socrata falso que devuelve las filas sin tocar la red."""

    class ClienteFake:
        def __init__(self):
            self.llamadas = []

        def get(self, dataset_id, **parametros):
            self.llamadas.append((dataset_id, parametros))
            return filas

    return ClienteFake()


def test_buscar_proveedores_usa_el_fixture_csv(monkeypatch):
    cliente = _cliente_fake(_filas_fixture())
    monkeypatch.setattr("src.fase2_secop_tools.Socrata", lambda *a, **k: cliente)

    resultado = buscar_proveedores_secop("software", "Bogotá DC")

    assert "software" in resultado
    assert "Proveedor" in resultado
    assert "Total ejecutado" in resultado
    assert "$ " in resultado
    assert "No se encontraron" not in resultado


def test_consulta_llega_con_filtro_soql(monkeypatch):
    cliente = _cliente_fake(_filas_fixture())
    monkeypatch.setattr("src.fase2_secop_tools.Socrata", lambda *a, **k: cliente)

    buscar_proveedores_secop("software", "Bogotá DC", codigo_unspsc="48101501")

    dataset_id, parametros = cliente.llamadas[0]
    assert dataset_id == "jbjy-vk9h"
    assert "objeto_del_contrato like '%software%'" in parametros["where"]
    assert "codigo_de_categoria_principal = '48101501'" in parametros["where"]
    assert parametros["limit"] == 100


def test_agrupa_y_ordena_por_total(monkeypatch):
    filas = [
        {"objeto_del_contrato": "software x", "departamento": "Distrito Capital de Bogotá",
         "valor_del_contrato": "1000", "proveedor_adjudicado": "Alfa", "documento_proveedor": "1"},
        {"objeto_del_contrato": "software y", "departamento": "Distrito Capital de Bogotá",
         "valor_del_contrato": "500", "proveedor_adjudicado": "Alfa", "documento_proveedor": "1"},
        {"objeto_del_contrato": "software z", "departamento": "Distrito Capital de Bogotá",
         "valor_del_contrato": "2000", "proveedor_adjudicado": "Beta", "documento_proveedor": "2"},
        {"objeto_del_contrato": "software w", "departamento": "Antioquia",
         "valor_del_contrato": "9999", "proveedor_adjudicado": "Gamma", "documento_proveedor": "3"},
    ]
    cliente = _cliente_fake(filas)
    monkeypatch.setattr("src.fase2_secop_tools.Socrata", lambda *a, **k: cliente)

    resultado = buscar_proveedores_secop("software", "Bogotá DC")

    # Beta (2000) antes que Alfa (1500); Gamma queda fuera por departamento
    assert resultado.index("Beta") < resultado.index("Alfa")
    assert "Gamma" not in resultado
    assert "$ 2.000" in resultado


def test_sin_resultados(monkeypatch):
    cliente = _cliente_fake([])
    monkeypatch.setattr("src.fase2_secop_tools.Socrata", lambda *a, **k: cliente)

    resultado = buscar_proveedores_secop("xyz", "Bogotá DC")
    assert "No se encontraron" in resultado