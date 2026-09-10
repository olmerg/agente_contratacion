# Fase 1 — Motor RAG sobre pliegos (documentación técnica)

Documento de referencia del módulo `src/fase1_rag_engine.py`. Está pensado para
quien mantiene el código (o para que el agente de IA construya la Fase 3 sobre
esta base). El estudiante no necesita leerlo.

---

## 1. Diseño

La Fase 1 es **retrieval puro (sin LLM)**: devuelve los top-k fragmentos más
relevantes con su fuente y página. El razonamiento y la extracción de datos
complejos (códigos UNSPSC, ítems…) lo hace el LLM de la Fase 3.

**Se usa LangChain como librería**; no hay lógica casera de lectura de PDFs ni
de indexación:

| Paso            | Componente (librería)               |
| --------------- | ------------------------------------ |
| Leer los PDFs   | `PyPDFLoader` (por página, guarda `source` y `page` en metadatos) |
| Partir en chunks| `RecursiveCharacterTextSplitter` (1000/200) |
| Indexar y buscar| `Chroma` de `langchain-chroma` (`add_documents`, `similarity_search_with_score`) |
| Embeddings      | `EmbeddingFunction` (adaptador de 6 líneas del embedding de ChromaDB a LangChain) |

Cada licitación tiene **su propia base vectorial** en `chroma_db/<licitacion>`.
No hace falta filtrar nada: la base aísla sola. La licitación se indica con
`--licitacion` en el CLI.

```python
PliegoRAG
├── indexar(carpeta_pdfs) -> dict          # reconstruye la BD de la licitación
├── esta_indexada() -> bool                # ¿la BD ya tiene chunks?
└── consultar_pliego(query, k=3) -> list   # top-k con texto, fuente, pagina, distancia

formatear_resultados(chunks) -> str        # función de módulo: Markdown para el LLM
```

`consultar_pliego` es la función que la Fase 3 envolverá con `@tool`.

## 2. Indexación

`indexar(carpeta_pdfs)`:
1. Carga todos los PDF (`.pdf`) de la carpeta con `PyPDFLoader`.
2. Los parte con `RecursiveCharacterTextSplitter` (chunk 1000, solape 200).
3. **Borra los chunks viejos** de esa licitación y agrega los nuevos
   (`add_documents`). Ejecutar dos veces no duplica.

> **Mejora pendiente:** distinguir PDFs nuevos de modificados para no re-indexar
> los que no cambiaron (hash MD5 del archivo en metadatos). Hoy se re-indexa
> toda la licitación.

## 3. Extracción por página

`PyPDFLoader` lee **página por página** y guarda el número en metadatos
(`page`, 0-based; se muestra 1-based). Fuente y página permiten citar
("ver página 247 del anexo técnico"), clave para la Fase 3.

## 4. Persistencia

Vectorial en `chroma_db/<licitacion>/` (una carpeta por proceso). Metadatos que
deja la librería en cada chunk: `source` (ruta del PDF) y `page`.

Embeddings: `paraphrase-multilingual-MiniLM-L12-v2` (multilingüe, rinde bien en
español; el default de ChromaDB, `all-MiniLM-L6-v2`, es monolingüe en inglés).

> El warning de deprecación de `langchain-community` (por el `PyPDFLoader`) se
> deja visible: es ruido aceptado a cambio de no depender de paquetes de
> extracción que requieren binarios nativos.

## 5. Interfaz

CLI de una sola operación. En cada llamada se indica la **licitación**:

```powershell
# Si esa licitación no está indexada, indexa su carpeta y luego responde
.\.venv\Scripts\python src\fase1_rag_engine.py "cuales son las licencias del lote 1" --licitacion IDARTES-SA-SI-013-2026

# Más chunks y otra carpeta base de licitaciones
.\.venv\Scripts\python src\fase1_rag_engine.py "soporte tecnico" --licitacion IDARTES-SA-SI-013-2026 --k 5 --carpetas datos\pliegos
```

Si la licitación ya tiene chunks, no re-indexa: solo consulta. Para
re-indexarla hay que borrar `chroma_db/<licitacion>/`.

## 6. Tests

```
tests/
├── helpers_pdfs.py                       # utilidades de PDF sintéticos (sin test_)
├── test_fase1_rag_engine.py              # unit tests, rápidos, sin ChromaDB
└── integration/
    └── test_fase1_rag_integracion.py     # integración = ChromaDB real + embeddings
```

### Unit tests (por defecto)

`tests/test_fase1_rag_engine.py` — `formatear_resultados` (Markdown, caso vacío,
múltiples chunks). Rápido y sin dependencias externas.

`.\.venv\Scripts\python -m pytest`

### Tests de integración (fuera del CD normal)

`tests/integration/test_fase1_rag_integracion.py` (marcados `integracion`). Usan
**ChromaDB real pero aislado** en el directorio temporal de pytest (`tmp_path`),
con PDFs sintéticos y el flujo completo de librería: indexación desde cero,
re-ejecución sin duplicar chunks, consulta semántica ordenada, **aislamiento
entre dos licitaciones** (bases separadas) y re-indexación tras modificar un
archivo.

Por defecto `pytest` los excluye (`addopts = "-m 'not integracion'"`), así el CD
solo corre unit tests rápidos y deterministas. La integración se corre aparte
(requiere descargar el modelo de embeddings la primera vez):

`.\.venv\Scripts\python -m pytest -m integracion`