"""Fase 0: Smoke Test - Verificar ChromaDB funcional con embeddings multilingües."""

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def main():
    print("cargando embeddings multilingües...")
    ef = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

    client = chromadb.Client()

    collection = client.create_collection("prueba_pliegos", embedding_function=ef)

    # Insertar 2 documentos de prueba
    collection.add(
        documents=[
            "El presente pliego establece las condiciones técnicas para la contratación de licencias de software",
            "Los lotes incluyen soporte técnico, mantenimiento preventivo y actualizaciones de seguridad",
            "Word es parte de la suite de Microsoft Office y requiere una licencia válida para su uso"
        ],
        metadatas=[
            {"fuente": "pliego_001.pdf", "seccion": "condiciones_tecnicas"},
            {"fuente": "pliego_002.pdf", "seccion": "soporte"},
            {"fuente": "pliego_003.pdf", "seccion": "software"}
        ],
        ids=["doc1", "doc2", "doc3"]
    )

    print(f"Documentos insertados: {collection.count()}")

    # Consulta de prueba
    resultados = collection.query(
        query_texts=["licencias de software"],
        n_results=3
    )

    print("\nResultados de la consulta:")
    for i, doc in enumerate(resultados["documents"][0]):
        fuente = resultados["metadatas"][0][i]["fuente"]
        distancia = resultados["distances"][0][i]
        print(f"  {i+1}. [{fuente}] (distancia: {distancia:.4f})")
        print(f"     {doc[:100]}...")

    print("\n[OK] Smoke test completado exitosamente")


if __name__ == "__main__":
    main()
