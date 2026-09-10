# Fase 1 — Motor RAG sobre pliegos (documentación técnica)

Documento de referencia del módulo `src/fase1_rag_engine.py`. Está pensado para
quien mantiene el código (o para que el agente de IA construya la Fase 3 sobre
esta base). El estudiante no necesita leerlo.

---

## 1. Diseño

La Fase 1 es **retrieval puro (sin LLM)**. Devuelve los top-k fragmentos más
relevantes con su fuente y página. El razonamiento y la extracción de datos
complejos (códigos UNSPSC, ítems, características técnicas) lo hace el LLM de la
Fase 3. Separar responsabilidades hace cada pieza testeable por su cuenta.

```python
PliegoRAG
├── cargar_e_indexar(folder_path) -> dict   # indexa PDFs nuevos/modificados
├── consultar_pliego(query, k=3) -> list    # top-k chunks: texto, fuente, pagina, distancia
└── formatear_resultados(chunks) -> str     # Markdown listo para inyectar al LLM
```

`consultar_pliego` es la función que la Fase 3 envolverá con `@tool`.

## 2. Carga incremental

La descarga de pliegos en SECOP II es **manual**. Por eso el indexador debe
soportar que se añadan documentos nuevos a `datos/pliegos/` sin re-indexar todo
desde cero:

1. Calcula el hash MD5 de cada PDF.
2. Compara contra lo ya indexado (`archivo_hash` guardado en metadatos).
3. PDF **nuevo** → se indexa.
4. PDF **sin cambios** → se omite.
5. PDF **modificado** → se eliminan sus chunks viejos y se re-indexa.

Esto también evita el error de `collection.add()` con ids duplicados al ejecutar
dos veces.

## 3. Extracción por página

Usa `pypdf` (y no `PyPDFDirectoryLoader`) para **leer página por página** y
guardar el número de página en metadatos. Eso permite citar con precisión
("ver página 247 del anexo técnico") y filtrar por sección, lo que es clave en la
Fase 3.

Se normalizan glifos que rompen la consola cp1252 de Windows y ensucian el texto
para el LLM: viñetas (`\uf0b7`), comillas tipográficas, guiones largos y espacios
no separables.

## 4. Fragmentación

`RecursiveCharacterTextSplitter` (`chunk_size=1000`, `overlap=200`) se aplica
**dentro de cada página**, no al documento completo. Así un fragmento nunca
mezcla dos páginas — importante en pliegos con tablas técnicas.

## 5. Persistencia

Vectorial en `chroma_db/` (persistente), colección `pliegos_secop`.

Metadatos por chunk:
| Campo          | Contenido                                   |
| -------------- | ------------------------------------------- |
| `fuente`       | Nombre del PDF                              |
| `pagina`       | Número de página (1-based)                  |
| `archivo_hash` | MD5 del PDF para la carga incremental       |

Embeddings: `paraphrase-multilingual-MiniLM-L12-v2` (multilingüe, rinde bien en
español; el default de ChromaDB, `all-MiniLM-L6-v2`, es monolingüe en inglés).

## 6. Interfaz

CLI interactiva: `python src/fase1_rag_engine.py` (o el script `secop-rag`).
Indexa, imprime el resumen y entra en un bucle de preguntas.

## 7. Tests unitarios

`tests/test_fase1_rag_engine.py` — 10 tests con **PDFs sintéticos** generados con
`fpdf2` (no dependen de los pliegos reales).

Cobertura:

- `_normalizar_texto`: limpieza de glifos.
- Indexación inicial (fuente, página, hash en metadatos).
- Carga incremental sin cambios → omite.
- PDF **nuevo** → lo indexa solo a él.
- PDF **modificado** → lo reemplaza.
- `consultar_pliego`: top-k, campos completos, orden por distancia.
- `k` mayor que el total → devuelve lo disponible.
- Relevancia semántica (el mejor resultado contiene las palabras clave).
- `formatear_resultados` y caso vacío.

**ChromaDB no se mockea**: cada test usa Chroma real pero aislado en el directorio
temporal de pytest (`tmp_path`), así la integración real (persistencia, dedupe,
consulta) queda validada sin tocar la `chroma_db/` del proyecto.

Ejecutar:

```powershell
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -v
```