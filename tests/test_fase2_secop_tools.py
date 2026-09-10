import csv
from pathlib import Path

from src.fase2_secop_tools import (
    _agrupar_por_proveedor,
    _aplicar_filtros,
    _construir_parametros,
    _departamento_coincide,
    _formatear_dinero,
    _formatear_markdown,
    _limpiar_valor,
    buscar_proveedores_secop,
)

FIXTURE = Path(__file__).parent / "data" / "secop_consulta_software.csv"


def _leer_fixture() -> list[dict]:
    with open(FIXTURE, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def test_construir_parametros_soql():
    params = _construir_parametros("software")
    assert "objeto_del_contrato like '%software%'" in params["$where"]
    assert params["$limit"] > 0


def test_construir_parametros_con_codigo_unspsc():
    params = _construir_parametros("software", codigo_unspsc="48101501")
    assert "codigo_de_categoria_principal = '48101501'" in params["$where"]


def test_limpiar_valor_tolera_formatos():
    assert _limpiar_valor("1.234.567,89") == 1234567.89
    assert _limpiar_valor("1,234,567.89") == 1234567.89
    assert _limpiar_valor("1234567.00") == 1234567.0
    assert _limpiar_valor("$ 5.000") == 5000.0
    assert _limpiar_valor("5.00") == 5.0
    assert _limpiar_valor("NaN") == 0.0
    assert _limpiar_valor(None) == 0.0


def test_departamento_coincide_tolera_variantes():
    assert _departamento_coincide("Bogotá DC", "Distrito Capital de Bogotá")
    assert _departamento_coincide("Valle del Cauca", "Valle del Cauca")
    assert not _departamento_coincide("Bogotá DC", "Antioquia")
    assert not _departamento_coincide("Bogotá DC", "No Definido")


def test_agrupar_por_proveedor_suma_y_ordena():
    filas = [
        {
            "objeto_del_contrato": "licencias de software",
            "departamento": "Distrito Capital de Bogotá",
            "valor_del_contrato": "1000",
            "proveedor_adjudicado": "Alfa",
            "documento_proveedor": "1",
        },
        {
            "objeto_del_contrato": "software educativo",
            "departamento": "Distrito Capital de Bogotá",
            "valor_del_contrato": "500.50",
            "proveedor_adjudicado": "Alfa",
            "documento_proveedor": "1",
        },
        {
            "objeto_del_contrato": "software",
            "departamento": "Distrito Capital de Bogotá",
            "valor_del_contrato": "2000",
            "proveedor_adjudicado": "Beta",
            "documento_proveedor": "2",
        },
    ]
    agrupados = _agrupar_por_proveedor(filas)

    assert [r["proveedor"] for r in agrupados] == ["Beta", "Alfa"]
    alfa = agrupados[1]
    assert alfa["contratos"] == 2
    assert alfa["total_ejecutado"] == 1500.5


def test_aplicar_filtros_filtra_departamento_y_termino():
    filas = [
        {
            "objeto_del_contrato": "software para la entidad",
            "departamento": "Distrito Capital de Bogotá",
            "codigo_de_categoria_principal": "48101501",
        },
        {
            "objeto_del_contrato": "software para la entidad",
            "departamento": "Antioquia",
            "codigo_de_categoria_principal": "48101501",
        },
        {
            "objeto_del_contrato": "servicios de aseo",
            "departamento": "Distrito Capital de Bogotá",
            "codigo_de_categoria_principal": "48101501",
        },
        {
            "objeto_del_contrato": "software para la entidad",
            "departamento": "Distrito Capital de Bogotá",
            "codigo_de_categoria_principal": "99999999",
        },
    ]
    resultado = _aplicar_filtros(filas, "software", "Bogotá DC", None)
    assert len(resultado) == 2
    assert all(r["departamento"] == "Distrito Capital de Bogotá" for r in resultado)

    resultado_unspsc = _aplicar_filtros(filas, "software", "Bogotá DC", "48101501")
    assert len(resultado_unspsc) == 1


def test_formatear_dinero():
    assert _formatear_dinero(1234567) == "$ 1.234.567"


def test_formatear_markdown_vacio():
    salida = _formatear_markdown([], "software", "Bogotá DC", 0)
    assert "No se encontraron" in salida


def test_buscar_proveedores_usa_el_fixture_csv(monkeypatch):
    filas_fixture = _leer_fixture()
    assert filas_fixture, "El fixture CSV debe tener filas reales descargadas"

    monkeypatch.setattr(
        "src.fase2_secop_tools._consultar_api", lambda _params: filas_fixture
    )
    resultado = buscar_proveedores_secop("software", "Bogotá DC")

    assert "software" in resultado
    assert "Proveedor" in resultado
    assert "Documento" in resultado
    assert "Total ejecutado" in resultado
    assert "No se encontraron" not in resultado
    assert "$ " in resultado


def test_buscar_proveedores_sin_resultados(monkeypatch):
    monkeypatch.setattr("src.fase2_secop_tools._consultar_api", lambda _params: [])
    resultado = buscar_proveedores_secop("xx", "Bogotá DC")
    assert "No se encontraron" in resultado