""" Fase 1nuestro objetivo es extraer la informacion de los pdf y guardarlo en chinks en chroma
"""
import argparse
import os


from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE = 1000 # caracteres
CHUNK_OVERLAP = 200 # caracteres

class EmbeddingFunction:
    def __init__(self):
        self.ef = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

    def embed_documentos(self, texts)->list:
        return self.ef(texts)
    def embed_query(self, text)->list:
        return self.ef([text])[0]
    
class PliegoRAG:
    def __init__(self, licitacion:str, chroma_dir: str ="chroma_db"):
        self.licitacion = licitacion
        self.directorio_db= os.path.join(chroma_dir,licitacion)
        self.vectorstore = Chroma(
            collection_name=self.licitacion,
            persist_directory=self.directorio_db,
            embedding_function=EmbeddingFunction()
        )
    
    def esta_creada(self)->bool:
        return len(self.vectorstore.get()["ids"]) > 0
    
    def indexar(self, carpeta_pdfs:str)->dict:
        pdfs = sorted([f for f in os.listdir(carpeta_pdfs) if f.endswith(".pdf")])
        if not pdfs:
            raise ValueError(f"No se encontraron archivos PDF en la carpeta: {carpeta_pdfs}")
        
        documentos = []
        for ruta in pdfs:
            documentos.append(PyPDFLoader(ruta).load())
        
        splittter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        chunks = splittter.split_documents(documentos)
        id_actuales = self.vectorstore._collection.get()["ids"]
        if id_actuales:
            print(f"Se encontraron {len(id_actuales)} documentos ya indexados. Se eliminarán antes de reindexar.")
            self.vectorstore._collection.delete(ids=id_actuales)
        self.vectorstore.add_documents(chunks)
        
        return {'pdfs': len(pdfs), 'chunks': len(chunks)}
    
    def consultar_pliego(self, query:str, k:int=3)->list[dict]:
        resultados = self.vectorstore.similarity_search_with_score(query, k=k)
        chunks = []
        for documento, score in resultados:
            chunks.append({
                'fuente': documento.metadata.get('source', 'desconocida'),
                'contenido': documento.page_content,
                'pagina': documento.metadata.get('page', 'desconocida')+1,
                'distancia': score
            })
        return chunks

def formatear_resultados(chunks:list[dict])->str:
    """Convierte los chunks en texto Markdown listo para la LLM"""
    if not chunks:
        return "No se encontraron resultados relevantes."
    
    resultado_formateado = "Resultados de la consulta:\n"
    for i, chunk in enumerate(chunks):
        resultado_formateado += (
            f"  {i+1}. [{chunk['fuente']}] (página: {chunk['pagina']}, distancia: {chunk['distancia']:.4f})\n"
            f"     {chunk['contenido']}\n"
        )
    return resultado_formateado

def main_cli():


    parser = argparse.ArgumentParser(description="Indexar y consultar pliegos de licitación en ChromaDB.")
    parser.add_argument("--licitacion", required=True, help="Nombre de la licitación (usado como nombre de colección).")
    parser.add_argument("--carpeta_pdfs", default="datos/pliegos", help="Ruta a la carpeta que contiene los archivos PDF.")
    parser.add_argument("--pregunta", help="Consulta para buscar en los pliegos indexados.")
    parser.add_argument("--k", type=int, default=3, help="Número de resultados a devolver para la consulta.")
    
    args = parser.parse_args()

    pliego_rag = PliegoRAG(args.licitacion)

    if not pliego_rag.esta_creada():
        print(f"Indexando pliegos desde {args.carpeta_pdfs}...")
        resultado_indexacion = pliego_rag.indexar(args.carpeta_pdfs)
        print(f"Indexación completada: {resultado_indexacion['pdfs']} PDFs procesados, {resultado_indexacion['chunks']} chunks creados.")
    else:
        print(f"La colección '{args.licitacion}' ya está creada y contiene documentos indexados.")

    if args.pregunta:
        print(f"\nConsultando: '{args.pregunta}'")
        resultados = pliego_rag.consultar_pliego(args.pregunta, k=args.k)
        print(formatear_resultados(resultados))
        
if __name__ == "__main__":
    main_cli()