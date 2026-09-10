import pytest

from src.fase1_rag_engine import PliegoRAG


@pytest.fixture
def rag(tmp_path):
    return PliegoRAG(
        chroma_dir=str(tmp_path / "chroma"),
        collection_name="coleccion_test",
    )