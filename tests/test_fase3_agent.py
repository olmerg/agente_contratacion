import os

import pytest

import src.fase3_agent as fase3


class PliegoRAGFake:
    def __init__(self, licitacion, indexada=True):
        self.licitacion = licitacion
        self.indexada = indexada
        self.indexado_path = None

    def esta_indexada(self):
        return self.indexada

    def indexar(self, path):
        self.indexado_path = path

    def consultar_pliego(self, pregunta, k=3):
        return [
            {
                "texto": "contenido del pliego",
                "fuente": "pliego_a.pdf",
                "pagina": 3,
                "distancia": 0.1234,
            }
        ]


def test_tool_rag_pliegos_usar_pliego_indexado(monkeypatch):
    rag = PliegoRAGFake("IDARTES-SA-SI-013-2026")
    monkeypatch.setattr(fase3, "PliegoRAG", lambda lic: rag)

    salida = fase3.tool_rag_pliegos.invoke(
        {"licitacion": "IDARTES-SA-SI-013-2026", "pregunta": "que licencias pide el Lote 2"}
    )

    assert "contenido del pliego" in salida
    assert "pliego_a.pdf" in salida
    assert "Pagina: 3" in salida
    assert rag.indexado_path is None  # no reindexa si ya esta indexado


def test_tool_rag_pliegos_indexa_si_falta(monkeypatch):
    rag = PliegoRAGFake("PROC-X", indexada=False)
    monkeypatch.setattr(fase3, "PliegoRAG", lambda lic: rag)

    fase3.tool_rag_pliegos.invoke(
        {"licitacion": "PROC-X", "pregunta": "requisitos"}
    )

    assert rag.indexado_path == os.path.join("datos", "pliegos", "PROC-X")


def test_tool_secop_proveedores_delega_a_fase2(monkeypatch):
    monkeypatch.setattr(
        fase3, "buscar_proveedores_secop", lambda *a, **k: "tabla de proveedores"
    )

    salida = fase3.tool_secop_proveedores.invoke(
        {"termino_clave": "software", "departamento": "Antioquia"}
    )

    assert salida == "tabla de proveedores"


def test_crear_agente_falla_sin_clave(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    with pytest.raises(SystemExit, match="NVIDIA_API_KEY"):
        fase3.crear_agente()


def test_crear_agente_expone_las_dos_herramientas(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-fake")

    agente = fase3.crear_agente()

    tools = agente.nodes["tools"].bound.tools_by_name
    assert "tool_rag_pliegos" in tools
    assert "tool_secop_proveedores" in tools