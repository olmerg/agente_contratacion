# Taller: Agente Inteligente de Contratación Estatal (SECOP II)

Un laboratorio de postgrado para aprender a construir un **agente conversacional
que analiza licitaciones públicas** en Colombia. El agente lee pliegos técnicos
en PDF (con RAG) y consulta datos abiertos de contratación estatal para
recomendar proveedores con experiencia.

---

## 1. Mapa del taller

```
┌─────────────────────────────────────────────────┐
│  RETO FINAL: preguntar al agente sobre una      │
│  licitación y recibir recomendación de           │
│  proveedores basada en datos reales              │
└─────────────────────────────────────────────────┘
                       ▲
┌─────────────────────────────────────────────────┐
│  FASE 3 ──▶ AGENTE ORQUESTADOR (LangChain +    │
│             NVIDIA Build API): unifica RAG y     │
│             datos abiertos en un solo agente     │
└─────────────────────────────────────────────────┘
                       ▲
┌─────────────────────────────────────────────────┐
│  FASE 2 ──▶ HERRAMIENTAS DE DATOS ABIERTOS:    │
│             consultar la API de SECOP II en      │
│             datos.gov.co (proveedores, montos)   │
└─────────────────────────────────────────────────┘
                       ▲
┌─────────────────────────────────────────────────┐
│  FASE 1 ──▶ MOTOR RAG: procesar PDFs de         │
│             pliegos, indexarlos en ChromaDB y     │
│             responder preguntas semánticas        │
└─────────────────────────────────────────────────┘
                       ▲
┌─────────────────────────────────────────────────┐
│  FASE 0 ──▶ SMOKE TEST: verificar que           │
│             ChromaDB funciona en local            │
└─────────────────────────────────────────────────┘
```

| Fase | Qué se construye                               | Estado          |
| ---- | ----------------------------------------------- | --------------- |
| 0    | Verificación de ChromaDB con documentos prueba | ✅ Implementado |
| 1    | Motor RAG sobre pliegos PDF                     | 🔲 Pendiente    |
| 2    | Tool de datos abiertos (API SECOP II)           | 🔲 Pendiente    |
| 3    | Agente orquestador con LangChain + NVIDIA       | 🔲 Pendiente    |

> **Filosofía del taller:** cada fase debe fallar rápido y con un mensaje
> claro si algo falta. Si el código "funciona" pero da resultados vacíos o
> silencia un error, el problema está enmascarado — investiga antes de seguir.

---

## 2. Estructura del proyecto

```
agente_contratacion/
├── .env                     # API key de NVIDIA (NO se sube a Git)
├── .env-example             # Plantilla del .env
├── .gitignore
├── pyproject.toml           # Dependencias del proyecto
├── README.md                # Este archivo
├── instrucciones.md         # Especificación técnica por fases
├── datos/
│   └── pliegos/             # PDFs descargados manualmente de SECOP II
│       └── IDARTES-SA-SI-013-2026/
│           ├── PLIEGO DE CONDICIONES.pdf
│           ├── 03. Anexo tecnico.pdf.pdf
│           └── 09_09_2026.pdf
├── chroma_db/               # Base de datos vectorial (se genera en Fase 1)
└── src/
    ├── __init__.py
    ├── fase0_smoke_test.py  # ✅ Verificación de ChromaDB
    ├── fase1_rag_engine.py  # Motor RAG sobre pliegos  ← tu tarea
    ├── fase2_secop_tools.py # Consumo de API SECOP II  ← tu tarea
    └── fase3_agent.py       # Agente LangChain + NVIDIA ← tu tarea
```

---

## 3. Instalación y ejecución

**Requisitos:** Python 3.10+, una clave de API de NVIDIA (gratuita en
[build.nvidia.com](https://build.nvidia.com)).

```powershell
# 1. Crear entorno virtual e instalar dependencias
python -m venv .venv
.\.venv\Scripts\pip install -e .

# 2. Crear el archivo .env con tu clave
copy .env-example .env
# Edita .env y pon tu clave real

# 3. Ejecutar la Fase 0 para verificar que todo está instalado
.\.venv\Scripts\python src\fase0_smoke_test.py
```

> **Nota:** la primera ejecución de ChromaDB descarga un modelo de embeddings
> (~79 MB). Esto es normal y solo ocurre la primera vez.

---

## 4. FASE 0 — Smoke Test (implementado)

**Objetivo:** verificar que ChromaDB está instalado correctamente y puede
insertar, indexar y consultar documentos.

### Qué hace

1. Crea un cliente efímero de ChromaDB (en memoria).
2. Inserta 2 documentos de prueba con sus metadatos (fuente, sección).
3. Ejecuta una consulta semántica: *"licencias de software"*.
4. Imprime los resultados ordenados por relevancia.

### Ejecutar

```powershell
.\.venv\Scripts\python src\fase0_smoke_test.py
```

Salida esperada:

```
Documentos insertados: 2

Resultados de la consulta:
  1. [pliego_001.pdf] (distancia: 0.xxxx)
     El presente pliego establece las condiciones técnicas...
  2. [pliego_002.pdf] (distancia: 0.xxxx)
     Los lotes incluyen soporte técnico...

✅ Smoke test completado exitosamente
```

### Discusión

- **¿Qué es un embedding?** Una representación numérica del texto que permite
  comparar significado sin palabras exactas.
- **¿Qué mide la distancia?** A menor distancia, mayor similitud semántica.
- **¿Qué cambia en la Fase 1?** Pasamos de documentos en memoria a PDFs
  reales en disco, con chunks y persistencia.

---

## 5. FASE 1 — Motor RAG sobre pliegos (por construir)

**Objetivo:** procesar PDFs de pliegos licitatorios, dividirlos en fragmentos,
indexarlos en ChromaDB y responder preguntas semánticas.

### Contratos de la implementación

Tu módulo debe exponer:

```python
class PliegoRAG:
    def __init__(self, licitacion: str, chroma_dir: str = "chroma_db"): ...
    def esta_indexada(self) -> bool: ...          # ¿ya hay chunks en la BD?
    def indexar(self, carpeta_pdfs: str) -> dict: # {"pdfs": int, "chunks": int}
    def consultar_pliego(self, query: str, k: int = 3) -> list[dict]: ...
    # cada dict: {"texto": str, "fuente": str, "pagina": int, "distancia": float}

def formatear_resultados(chunks: list[dict]) -> str: ...  # Markdown para el LLM
```

### Ejercicios guiados

1. **Carga de PDFs.** Usa `PyPDFLoader` (no `PyPDFDirectoryLoader`) para leer
   PDF por PDF y que cada página conserve `source` y `page` en sus metadatos.
2. **Fragmentación.** Divide con `RecursiveCharacterTextSplitter`
   (chunk_size=1000, overlap=200). ¿Por qué no enviar el PDF entero al LLM?
3. **Indexación persistente.** Cada licitación tiene su propia carpeta en
   `chroma_db/<licitacion>/`. Así no mezclas contratos distintos.
4. **Consulta.** `similarity_search_with_score` devuelve el texto y la
   distancia. A menor distancia → mayor relevancia.

> **Trampa común:** si llamas `indexar()` dos veces sobre la misma licitación
> sin limpiar la colección antes, los chunks se duplican. Asegúrate de borrar
> los ids existentes antes de agregar los nuevos.

### Verificar

```powershell
# Indexa los PDFs y responde la pregunta
.\.venv\Scripts\python src\fase1_rag_engine.py "cuales son las licencias del lote 1" --licitacion IDARTES-SA-SI-013-2026
```

---

## 6. FASE 2 — Datos abiertos SECOP II (por construir)

**Objetivo:** consumir la API SODA de datos.gov.co para encontrar proveedores
con experiencia en contratación estatal.

### Contrato de la implementación

```python
def buscar_proveedores_secop(
    termino_clave: str,
    departamento: str = "Bogotá DC",
    codigo_unspsc: str | None = None,
) -> str:
    """Retorna una tabla Markdown con proveedores, #contratos y total ejecutado."""
```

### Ejercicios guiados

1. **Consulta SoQL.** Construye el filtro `objeto_del_contrato LIKE '%term%'`
   y añade `codigo_de_categoria_principal` si viene el código UNSPSC.
2. **Limpieza.** `valor_del_contrato` viene como texto; conviértelo a numérico
   con `pd.to_numeric(..., errors="coerce")` antes de sumar.
3. **Agrupación.** Agrupa por `proveedor_adjudicado` + `documento_proveedor`
   y calcula `count` (contratos) y `sum` (total ejecutado).
4. **Formato.** Retorna una tabla Markdown: el LLM de la Fase 3 la va a leer
   directamente.

> **Nota de seguridad (para discutir en clase):** el término de búsqueda se
> interpola directamente en la consulta SoQL. ¿Qué pasaría si alguien pasa
> `software' OR '1'='1`? ¿Cómo lo mitigarías?

### Verificar

```powershell
# Lista proveedores de 'software' en Bogotá
.\.venv\Scripts\python src\fase2_secop_tools.py "software" --departamento "Bogotá DC"

# Filtro adicional por categoría UNSPSC
.\.venv\Scripts\python src\fase2_secop_tools.py "software" --departamento "Bogotá DC" --codigo-unspsc 48101501
```

> Sin `SECOP_APP_TOKEN` en el `.env` sodapy mostrará un aviso de límites de
> tráfico. Es informativo, no un error: el script sigue funcionando.

---

## 7. FASE 3 — Agente orquestador (por construir)

**Objetivo:** integrar RAG + datos abiertos en un agente LangChain propulsado
por NVIDIA Build API. El agente decide qué herramienta usar según la pregunta.

### Contratos de la implementación

```python
@tool
def tool_rag_pliegos(licitacion: str, pregunta: str) -> str: ...

@tool
def tool_secop_proveedores(termino_clave: str, departamento: str, ...) -> str: ...

def crear_agente(): ...   # falla rápido si falta NVIDIA_API_KEY
def responder(agente, pregunta: str, thread_id: str) -> str: ...
```

### El flujo del agente

1. El usuario hace una pregunta sobre la licitación.
2. El agente invoca `tool_rag_pliegos` para leer el pliego (Fase 1).
3. Con las palabras clave o códigos UNSPSC identificados, invoca
   `tool_secop_proveedores` en datos abiertos (Fase 2).
4. Responde en español citando fuente y página.

### Puntos clave de implementación

- **Memoria conversacional:** usa `MemorySaver` y `thread_id` para mantener
  contexto entre preguntas en la misma sesión.
- **Recursion limit:** limita a ~12 iteraciones para evitar loops del agente.
- **`create_agent` vs `create_react_agent`:** en LangChain 1.x el wrapper
  recomendado es `create_agent` (arma un grafo LangGraph por debajo).
- **Thinking mode:** si usas Nemotron, desactiva el razonamiento interno con
  `model_kwargs={"chat_template_kwargs": {"enable_thinking": False}}` para
  respuestas deterministas y rápidas.

### Verificar

```powershell
# Una sola pregunta
.\.venv\Scripts\python -m src.fase3_agent "que licencias pide el Lote 2 del pliego IDARTES-SA-SI-013-2026?"

# Modo interactivo (mantiene contexto entre preguntas)
.\.venv\Scripts\python -m src.fase3_agent
```

### Pregunta de evaluación sugerida

> *"Revisa el anexo técnico y dime qué licencias se solicitan para el Lote 2.
> Con base en eso, busca en Datos Abiertos qué proveedores han entregado ese
> tipo de software en Bogotá y ordénalos por valor contratado."*

El agente debe hacer **2 tool calls automáticos** y responder de forma
estructurada en español.

---

> **Aviso académico:** los datos de proveedores en el taller son de fuentes
> públicas (datos.gov.co). Los pliegos en `datos/pliegos/` son documentos
> públicos descargados de SECOP II. Nunca subas datos personales reales
> (Ley 1581 de 2012).
