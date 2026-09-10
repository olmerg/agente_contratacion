"""Fase 1: Motor RAG sobre pliegos licitatorios con ChromaDB.

Retrieval puro (sin LLM): indexa PDFs por página y devuelve los chunks más
relevantes con su fuente y página. El razonamiento queda para la Fase 3.

La carga es incremental: nuevos PDFs en la carpeta se indexan sin re-indexar
los existentes. Los PDFs modificados se re-indexan (su versión anterior se
elimina). Los pliegos se descargan manualmente en datos/pliegos/.
"""

import glob
import hashlib
import os
import re

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

_GLIFOS = {
    "\uf0b7": "-",
    "\u2022": "-",
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u00a0": " ",
}


def _normalizar_texto(texto: str) -> str:
    for glifo, reemplazo in _GLIFOS.items():
        texto = texto.replace(glifo, reemplazo)
    texto = re.sub(r"[ \t]+", " ", texto)
    return texto.strip()


class PliegoRAG:
    def __init__(
        self,
        chroma_dir: str = "chroma_db",
        collection_name: str = "pliegos_secop",
    ):
        self.embedding_function = SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        self.client = chromadb.PersistentClient(path=chroma_dir)
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", ",", " "],
        )

    def _hash_archivo(self, ruta_pdf: str) -> str:
        h = hashlib.md5()
        with open(ruta_pdf, "rb") as f:
            for bloque in iter(lambda: f.read(8192), b""):
                h.update(bloque)
        return h.hexdigest()

    def _fuentes_indexadas(self) -> dict[str, str]:
        """Devuelve {fuente: hash_archivo} de lo ya indexado."""

        resultados = self.collection.get(include=["metadatas"])
        fuentes = {}
        for meta in resultados.get("metadatas", []):
            if meta:
                fuentes[meta["fuente"]] = meta["archivo_hash"]
        return fuentes

    def _leer_paginas(self, ruta_pdf: str) -> list[dict]:
        texto_paginas = []
        try:
            reader = PdfReader(ruta_pdf)
        except Exception as e:
            print(f"  [skip] {ruta_pdf}: {e}")
            return texto_paginas

        for i, pagina in enumerate(reader.pages):
            texto = _normalizar_texto(pagina.extract_text() or "")
            if texto:
                texto_paginas.append({"texto": texto, "pagina": i + 1})
        return texto_paginas

    def _indexar_archivo(self, ruta_pdf: str, fuente: str, archivo_hash: str) -> int:
        paginas = self._leer_paginas(ruta_pdf)
        if not paginas:
            return 0

        total_chunks = 0
        for pagina in paginas:
            chunks = self.splitter.split_text(pagina["texto"])
            if not chunks:
                continue

            self.collection.add(
                documents=chunks,
                metadatas=[
                    {
                        "fuente": fuente,
                        "pagina": pagina["pagina"],
                        "archivo_hash": archivo_hash,
                    }
                ]
                * len(chunks),
                ids=[
                    f"{fuente}-p{pagina['pagina']}-{j}"
                    for j in range(len(chunks))
                ],
            )
            total_chunks += len(chunks)
        return total_chunks

    def cargar_e_indexar(self, folder_path: str) -> dict:
        """Indexa los PDFs nuevos o modificados de folder_path (recursivo).

        Devuelve {"indexados": int, "omitidos": int, "reemplazados": int}.
        """

        pdfs = sorted(
            glob.glob(os.path.join(folder_path, "**", "*.pdf"), recursive=True)
        )
        if not pdfs:
            raise ValueError(f"No hay PDFs en {folder_path}")

        fuentes_indexadas = self._fuentes_indexadas()
        resumen = {"indexados": 0, "omitidos": 0, "reemplazados": 0}

        for ruta_pdf in pdfs:
            fuente = os.path.basename(ruta_pdf)
            archivo_hash = self._hash_archivo(ruta_pdf)

            if fuente in fuentes_indexadas:
                if fuentes_indexadas[fuente] == archivo_hash:
                    resumen["omitidos"] += 1
                    continue
                self.collection.delete(where={"fuente": fuente})
                resumen["reemplazados"] += 1

            n = self._indexar_archivo(ruta_pdf, fuente, archivo_hash)
            if n:
                resumen["indexados"] += 1
                print(f"  + {fuente} ({n} chunks)")

        return resumen

    def consultar_pliego(self, query: str, k: int = 3) -> list[dict]:
        """Devuelve los k chunks más relevantes con texto, fuente, página y distancia."""

        resultados = self.collection.query(
            query_texts=[query],
            n_results=k,
        )

        chunks = []
        for i in range(len(resultados["documents"][0])):
            chunks.append(
                {
                    "texto": resultados["documents"][0][i],
                    "fuente": resultados["metadatas"][0][i]["fuente"],
                    "pagina": resultados["metadatas"][0][i]["pagina"],
                    "distancia": resultados["distances"][0][i],
                }
            )
        return chunks

    def formatear_resultados(self, chunks: list[dict]) -> str:
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


def main_cli(carpetas: str = "datos/pliegos") -> None:
    rag = PliegoRAG()

    resumen = rag.cargar_e_indexar(carpetas)
    total = rag.collection.count()
    print(
        f"Indexados: {resumen['indexados']} | Omitidos: {resumen['omitidos']} "
        f"| Reemplazados: {resumen['reemplazados']} | Total chunks: {total}"
    )

    while True:
        pregunta = input("\nPregunta sobre el pliego (q para salir): ").strip()
        if pregunta.lower() == "q":
            break

        resultado = rag.consultar_pliego(pregunta, k=3)
        print("\n" + rag.formatear_resultados(resultado))


if __name__ == "__main__":
    main_cli()