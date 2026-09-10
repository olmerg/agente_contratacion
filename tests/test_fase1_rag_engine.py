from src.fase1_rag_engine import formatear_resultados


def test_formatear_resultados():
    chunks = [
        {
            "texto": "contenido del pliego",
            "fuente": "pliego_a.pdf",
            "pagina": 3,
            "distancia": 0.1234,
        }
    ]
    salida = formatear_resultados(chunks)
    assert "pliego_a.pdf" in salida
    assert "Pagina: 3" in salida
    assert "0.1234" in salida
    assert "contenido del pliego" in salida


def test_formatear_resultados_vacio():
    assert formatear_resultados([]) == "No se encontraron resultados."


def test_formatear_resultados_varios_chunks():
    chunks = [
        {
            "texto": "primer",
            "fuente": "a.pdf",
            "pagina": 1,
            "distancia": 0.2100,
        },
        {
            "texto": "segundo",
            "fuente": "b.pdf",
            "pagina": 2,
            "distancia": 0.4100,
        },
    ]
    salida = formatear_resultados(chunks)
    assert "[1]" in salida and "[2]" in salida
    assert "0.2100" in salida and "0.4100" in salida