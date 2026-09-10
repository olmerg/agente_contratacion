"""Fase 1: Motor RAG sobre pliegos licitatorios con LangChain.

Retrieval puro (sin LLM): cada licitación tiene su propia base vectorial en
chroma_db/<licitacion>. Cargar PDFs, partir en chunks, indexar y buscar lo hace
LangChain; aquí solo se configura y se da formato a la salida.
"""

import argparse
import glob
import os

from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


class EmbeddingFunction:
    """Adaptador: langchain_chroma espera embed_documents/embed_query.

    Envuelve el embedding de ChromaDB para usarlo como función de LangChain.
    """

    def __init__(self, model_name: str):
        self._embedding = SentenceTransformerEmbeddingFunction(
            model_name=model_name
        )

    def embed_documents(self, textos) -> list:
        return self._embedding(textos)

    def embed_query(self, query: str) -> list:
        return self._embedding([query])[0]


class PliegoRAG:
    def __init__(self, licitacion: str, chroma_dir: str = "chroma_db"):
        self.licitacion = licitacion
        self.directorio_db = os.path.join(chroma_dir, licitacion)
        self.vectorstore = Chroma(
            collection_name=licitacion,
            persist_directory=self.directorio_db,
            embedding_function=EmbeddingFunction(EMBEDDING_MODEL),
        )

    def esta_indexada(self) -> bool:
        return self.vectorstore._collection.count() > 0

    def indexar(self, carpeta_pdfs: str) -> dict:
        """Reconstruye la base de la licitación desde los PDFs de carpeta_pdfs.

        Carga los PDFs (PyPDFLoader), los parte en chunks y los indexa
        (add_documents). Devuelve {"pdfs": int, "chunks": int}.
        """

        pdfs = sorted(
            glob.glob(os.path.join(carpeta_pdfs, "*.pdf"))
        )
        if not pdfs:
            raise ValueError(f"No hay PDFs en {carpeta_pdfs}")

        documentos = []
        for ruta in pdfs:
            documentos.extend(PyPDFLoader(ruta).load())

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
        chunks = splitter.split_documents(documentos)

        ids_actuales = self.vectorstore._collection.get()["ids"]
        if ids_actuales:
            self.vectorstore._collection.delete(ids=ids_actuales)
        self.vectorstore.add_documents(chunks)

        return {"pdfs": len(pdfs), "chunks": len(chunks)}

    def consultar_pliego(self, query: str, k: int = 3) -> list[dict]:
        """Devuelve los k chunks más relevantes con texto, fuente, página y distancia."""

        resultados = self.vectorstore.similarity_search_with_score(query, k=k)
        chunks = []
        for documento, score in resultados:
            chunks.append(
                {
                    "texto": documento.page_content,
                    "fuente": os.path.basename(documento.metadata["source"]),
                    "pagina": documento.metadata["page"] + 1,
                    "distancia": score,
                }
            )
        return chunks


def formatear_resultados(chunks: list[dict]) -> str:
    """Convierte los chunks en texto Markdown listo para inyectar al LLM."""

    if not chunks:
        return "No se encontraron resultados."

    lineas = []
    for i, chunk in enumerate(chunks, 1):
        lineas.append(
            f"[{i}] Fuente: {chunk['fuente']} | Pagina: {chunk['pagina']} "
            f"| Distancia: {chunk['distancia']:.4f}\n{chunk['texto']}"
        )
    return "\n\n".join(lineas)


def main_cli() -> None:
    parser = argparse.ArgumentParser(
        description="Consulta RAG sobre pliegos SECOP II"
    )
    parser.add_argument("pregunta", help="Pregunta sobre el pliego")
    parser.add_argument(
        "--licitacion",
        required=True,
        help="Carpeta del proceso en --carpetas (ej: IDARTES-SA-SI-013-2026)",
    )
    parser.add_argument(
        "--k", type=int, default=3, help="Numero de chunks a recuperar"
    )
    parser.add_argument(
        "--carpetas",
        default="datos/pliegos",
        help="Carpeta base donde estan las licitaciones",
    )
    args = parser.parse_args()

    ruta_licitacion = os.path.join(args.carpetas, args.licitacion)
    if not os.path.isdir(ruta_licitacion):
        raise SystemExit(f"No existe la licitacion: {ruta_licitacion}")

    rag = PliegoRAG(args.licitacion)
    if not rag.esta_indexada():
        resumen = rag.indexar(ruta_licitacion)
        print(f"Indexados: {resumen['pdfs']} PDFs | {resumen['chunks']} chunks")

    resultado = rag.consultar_pliego(args.pregunta, k=args.k)
    print(formatear_resultados(resultado))


if __name__ == "__main__":
    main_cli()