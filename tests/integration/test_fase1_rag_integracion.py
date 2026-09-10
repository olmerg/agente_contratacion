import pytest

from helpers_pdfs import PLIEGO_A, PLIEGO_B, crear_pdf

from src.fase1_rag_engine import PliegoRAG, formatear_resultados

pytestmark = pytest.mark.integracion


@pytest.fixture
def rag(tmp_path):
    return PliegoRAG("proceso-001", chroma_dir=str(tmp_path / "chroma"))


def _carpeta_licitacion(tmp_path, nombre):
    carpeta = tmp_path / "pliegos" / nombre
    carpeta.mkdir(parents=True)
    return carpeta


def test_indexacion_desde_cero(rag, tmp_path):
    carpeta = _carpeta_licitacion(tmp_path, "proceso-001")
    crear_pdf(carpeta / "pliego_a.pdf", PLIEGO_A)
    crear_pdf(carpeta / "pliego_b.pdf", PLIEGO_B)

    resumen = rag.indexar(str(carpeta))
    assert resumen["pdfs"] == 2
    assert resumen["chunks"] > 0
    assert rag.vectorstore._collection.count() == resumen["chunks"]
    assert rag.esta_indexada()


def test_reejecucion_no_duplica_chunks(rag, tmp_path):
    carpeta = _carpeta_licitacion(tmp_path, "proceso-001")
    crear_pdf(carpeta / "pliego_a.pdf", PLIEGO_A)
    crear_pdf(carpeta / "pliego_b.pdf", PLIEGO_B)

    rag.indexar(str(carpeta))
    total = rag.vectorstore._collection.count()

    resumen = rag.indexar(str(carpeta))
    assert resumen["pdfs"] == 2
    assert rag.vectorstore._collection.count() == total


def test_consulta_semantica_ordenada_con_formato(rag, tmp_path):
    carpeta = _carpeta_licitacion(tmp_path, "proceso-001")
    crear_pdf(carpeta / "pliego_a.pdf", PLIEGO_A)
    crear_pdf(carpeta / "pliego_b.pdf", PLIEGO_B)
    rag.indexar(str(carpeta))

    resultados = rag.consultar_pliego("licencias de software de arquitectura", k=2)
    assert len(resultados) == 2
    for r in resultados:
        assert {"texto", "fuente", "pagina", "distancia"} <= set(r)
        assert r["pagina"] >= 1
    distancias = [r["distancia"] for r in resultados]
    assert distancias == sorted(distancias)

    salida = formatear_resultados(resultados)
    assert "Pagina:" in salida


def test_licitaciones_aisladas_en_bases_separadas(tmp_path):
    carpeta_a = _carpeta_licitacion(tmp_path, "proceso-001")
    crear_pdf(carpeta_a / "pliego_a.pdf", PLIEGO_A)
    crear_pdf(carpeta_a / "pliego_b.pdf", PLIEGO_B)
    rag_a = PliegoRAG("proceso-001", chroma_dir=str(tmp_path / "chroma"))
    rag_a.indexar(str(carpeta_a))

    carpeta_b = _carpeta_licitacion(tmp_path, "proceso-002")
    crear_pdf(carpeta_b / "unico.pdf", ["DOCUMENTO EXCLUSIVO DEL PROCESO DOS"] * 5)
    rag_b = PliegoRAG("proceso-002", chroma_dir=str(tmp_path / "chroma"))
    rag_b.indexar(str(carpeta_b))

    assert rag_a.esta_indexada()
    assert rag_b.esta_indexada()

    solo_a = rag_a.consultar_pliego("documento exclusivo del proceso", k=3)
    assert len(solo_a) == 2
    assert all("EXCLUSIVO" not in r["texto"].upper() for r in solo_a)

    solo_b = rag_b.consultar_pliego("documento exclusivo del proceso", k=1)
    assert "EXCLUSIVO" in solo_b[0]["texto"].upper()


def test_reindexacion_completa_tras_modificar_archivo(rag, tmp_path):
    carpeta = _carpeta_licitacion(tmp_path, "proceso-001")
    crear_pdf(carpeta / "pliego_a.pdf", PLIEGO_A)
    crear_pdf(carpeta / "pliego_b.pdf", PLIEGO_B)
    rag.indexar(str(carpeta))

    crear_pdf(carpeta / "pliego_b.pdf", ["CONTENIDO COMPLETAMENTE DISTINTO"] * 8)
    rag.indexar(str(carpeta))

    resultados = rag.consultar_pliego("lote 2 diseno audiovisual", k=5)
    assert "COMPLETAMENTE DISTINTO" not in resultados[0]["texto"].upper()