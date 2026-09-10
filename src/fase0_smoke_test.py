"""Fase 0: Smoke Test - Verificar ChromaDB funcional."""

import chromadb


def main():
    # Cliente efímero (en memoria)
    client = chromadb.Client()

    # Crear colección
    collection = client.create_collection("prueba_pliegos")

    # Insertar 2 documentos de prueba
    collection.add(
        documents=[
            "El presente pliego establece las condiciones técnicas para la contratación de licencias de software",
            "Los lotes incluyen soporte técnico, mantenimiento preventivo y actualizaciones de seguridad"
        ],
        metadatas=[
            {"fuente": "pliego_001.pdf", "seccion": "condiciones_tecnicas"},
            {"fuente": "pliego_002.pdf", "seccion": "soporte"}
        ],
        ids=["doc1", "doc2"]
    )

    print(f"Documentos insertados: {collection.count()}")

    # Consulta de prueba
    resultados = collection.query(
        query_texts=["licencias de software"],
        n_results=2
    )

    print("\nResultados de la consulta:")
    for i, doc in enumerate(resultados["documents"][0]):
        fuente = resultados["metadatas"][0][i]["fuente"]
        distancia = resultados["distances"][0][i]
        print(f"  {i+1}. [{fuente}] (distancia: {distancia:.4f})")
        print(f"     {doc[:100]}...")

    print("\n✅ Smoke test completado exitosamente")


if __name__ == "__main__":
    main()
