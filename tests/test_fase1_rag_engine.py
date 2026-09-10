from fpdf import FPDF
from src.fase1_rag_engine import PliegoRAG, _normalizar_texto


def crear_pdf(ruta, lineas):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    for linea in lineas:
        pdf.cell(0, 6, linea.encode("latin-1", errors="replace").decode("latin-1"))
        pdf.ln()
    pdf.output(str(ruta))


PLIEGO_A = [
    "PLIEGO DE CONDICIONES LOTE 1",
    "El objeto es la adquisicion de licencias de software de arquitectura.",
    "El proponente debe acreditar soporte tecnico y mantenimiento.",
    "El plazo de ejecucion es de doce meses.",
]

PLIEGO_B = [
    "LOTE 2 ACTUALIZACION DE SOFTWARE",
    "Se solicitan licencias de diseno y produccion audiovisual.",
    "El contratista entregara capacitacion al personal de la entidad.",
    "El valor estimado es de doscientos millones de pesos.",
]


def _coleccion_datos(rag, tmp_path):
    """Indexa 2 PDFs sinteticos (uno en subcarpeta) y devuelve la ruta."""
    raiz = tmp_path / "pliegos"
    sub = raiz / "proceso-001"
    sub.mkdir(parents=True)
    crear_pdf(sub / "pliego_a.pdf", PLIEGO_A)
    crear_pdf(raiz / "pliego_b.pdf", PLIEGO_B)
    return raiz


def test_normalizar_texto():
    texto = "\uf0b7 item uno\u00a0con  \tespacios  \n\u201ccomilla\u201d"
    resultado = _normalizar_texto(texto)
    assert "\uf0b7" not in resultado
    assert "\u00a0" not in resultado
    assert "\u201c" not in resultado


def test_indexacion_inicial(rag, tmp_path):
    raiz = _coleccion_datos(rag, tmp_path)
    resumen = rag.cargar_e_indexar(str(raiz))
    assert resumen["indexados"] == 2
    assert rag.collection.count() > 0
    metas = rag.collection.get(include=["metadatas"])["metadatas"]
    assert all(m["archivo_hash"] for m in metas)
    assert {m["fuente"] for m in metas} == {"pliego_a.pdf", "pliego_b.pdf"}


def test_indexacion_incremental_omite_sin_cambios(rag, tmp_path):
    raiz = _coleccion_datos(rag, tmp_path)
    rag.cargar_e_indexar(str(raiz))
    total = rag.collection.count()
    resumen = rag.cargar_e_indexar(str(raiz))
    assert resumen["omitidos"] == 2
    assert resumen["indexados"] == 0
    assert rag.collection.count() == total


def test_indexacion_nuevo_pdf(rag, tmp_path):
    raiz = _coleccion_datos(rag, tmp_path)
    rag.cargar_e_indexar(str(raiz))
    total = rag.collection.count()

    crear_pdf(raiz / "pliego_c.pdf", ["DOCUMENTO NUEVO ADICIONAL"] * 5)
    resumen = rag.cargar_e_indexar(str(raiz))
    assert resumen["indexados"] == 1
    assert resumen["omitidos"] == 2
    assert rag.collection.count() > total


def test_reindexacion_archivo_modificado(rag, tmp_path):
    raiz = _coleccion_datos(rag, tmp_path)
    rag.cargar_e_indexar(str(raiz))

    crear_pdf(raiz / "pliego_b.pdf", ["CONTENIDO COMPLETAMENTE DISTINTO"] * 8)
    resumen = rag.cargar_e_indexar(str(raiz))
    assert resumen["reemplazados"] == 1
    resultados = rag.consultar_pliego("lote 2 diseno audiovisual", k=5)
    assert "COMPLETAMENTE DISTINTO" not in resultados[0]["texto"].upper()


def test_consultar_pliego_devuelve_top_k(rag, tmp_path):
    raiz = _coleccion_datos(rag, tmp_path)
    rag.cargar_e_indexar(str(raiz))

    resultados = rag.consultar_pliego("licencias de software", k=2)
    assert len(resultados) == 2
    for r in resultados:
        assert {"texto", "fuente", "pagina", "distancia"} <= set(r)
        assert r["pagina"] >= 1
        assert r["fuente"] in {"pliego_a.pdf", "pliego_b.pdf"}
    distancias = [r["distancia"] for r in resultados]
    assert distancias == sorted(distancias)


def test_consultar_pliego_devuelve_disponibles_si_k_excede(rag, tmp_path):
    raiz = _coleccion_datos(rag, tmp_path)
    rag.cargar_e_indexar(str(raiz))

    resultados = rag.consultar_pliego("licencias", k=10)
    assert len(resultados) == 2


def test_consultar_pliego_relevancia_semantica(rag, tmp_path):
    raiz = _coleccion_datos(rag, tmp_path)
    rag.cargar_e_indexar(str(raiz))

    mejores = rag.consultar_pliego("software de arquitectura lote 1", k=2)
    assert "arquitectura" in mejores[0]["texto"].lower()


def test_formatear_resultados(rag):
    chunks = [
        {
            "texto": "contenido del pliego",
            "fuente": "pliego_a.pdf",
            "pagina": 3,
            "distancia": 0.1234,
        }
    ]
    salida = rag.formatear_resultados(chunks)
    assert "pliego_a.pdf" in salida
    assert "Pagina: 3" in salida
    assert "0.1234" in salida
    assert "contenido del pliego" in salida


def test_formatear_resultados_vacio(rag):
    assert rag.formatear_resultados([]) == "No se encontraron resultados."