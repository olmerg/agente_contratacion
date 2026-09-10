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

| Fase | Qué se construye                                | Estado        |
| ---- | ----------------------------------------------- | ------------- |
| 0    | Verificación de ChromaDB con documentos prueba  | ✅ Implementado|
| 1    | Motor RAG sobre pliegos PDF                     | ✅ Implementado|
| 2    | Tool de datos abiertos (API SECOP II)           | 🔲 Pendiente  |
| 3    | Agente orquestador con LangChain + NVIDIA       | 🔲 Pendiente  |

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
    ├── fase1_rag_engine.py  # Motor RAG sobre pliegos
    ├── fase2_secop_tools.py # Consumo de API SECOP II
    └── fase3_agent.py       # Agente LangChain + NVIDIA
```

---

## 3. Instalación y ejecución

**Requisitos:** Python 3.10+, una clave de API de NVIDIA (gratuita en
[build.nvidia.com](https://build.nvidia.com)).

```powershell
# 1. Crear entorno virtual e instalar dependencias
python -m venv .venv
.\.venv\Scripts\pip install -e .

# 1b. (opcional) Dependencias de desarrollo para correr los tests
.\.venv\Scripts\pip install -e ".[dev]"

# 2. Crear el archivo .env con tu clave
copy .env-example .env
# Edita .env y pon tu clave real

# 3. Ejecutar la fase que corresponda
.\.venv\Scripts\python src\fase0_smoke_test.py
.\.venv\Scripts\python src\fase1_rag_engine.py

# 4. Ejecutar los tests unitarios
.\.venv\Scripts\python -m pytest
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

## 5. FASE 1 — Motor RAG sobre pliegos (implementado)

**Objetivo:** procesar PDFs de pliegos licitatorios, dividirlos en fragmentos,
indexarlos en ChromaDB y recuperar los fragmentos más relevantes ante una
pregunta.

> **Nota de diseño:** la Fase 1 es **retrieval puro** (sin LLM). Devuelve los
> top-k fragmentos con su fuente y página. El razonamiento y la extracción de
> datos complejos (códigos UNSPSC, ítems, características técnicas) lo hace el
> LLM de la Fase 3.

### Qué hace

1. **Carga incremental.** Recorre `datos/pliegos/` (recursivo), calcula el hash
   de cada PDF y solo indexa los **nuevos o modificados**. Descargar un pliego
   nuevo a la carpeta y volver a ejecutar es suficiente.
2. **Extracción por página.** Usa `pypdf` para leer cada PDF página por página,
   normalizando glifos problemáticos (viñetas, comillas tipográficas).
3. **Fragmentación.** `RecursiveCharacterTextSplitter` (chunk_size=1000,
   overlap=200) dentro de cada página, para que un fragmento nunca mezcle dos
   páginas.
4. **Persistencia.** Los vectores quedan en `chroma_db/` con metadatos:
   `fuente` (nombre del PDF), `pagina` y `archivo_hash`.
5. **Consulta.** Retorna top-k fragmentos con texto, fuente, página y distancia.

### Ejecutar

```powershell
.\.venv\Scripts\python src\fase1_rag_engine.py
```

Salida esperada al indexar:

```
  + PLIEGO DE CONDICIONES.pdf (212 chunks)
  + 09_09_2026.pdf (48 chunks)
  + 03. Anexo tecnico.pdf.pdf (51 chunks)
Indexados: 3 | Omitidos: 0 | Reemplazados: 0 | Total chunks: 311
```

Luego escribe preguntas en la consola:

```
Pregunta sobre el pliego (q para salir): Que licencias se solicitan para el Lote 2

[1] Fuente: 09_09_2026.pdf | Pagina: 6 | Distancia: 0.2930
Incluye las siguientes licencias:
- Genially Master
- Genially Edu Pro
- StreamYard
...
```

### Tests unitarios

Los tests generan PDFs sintéticos (sin depender de los pliegos reales) y
verifican: indexación inicial, carga incremental, detección de archivos
modificados, relevancia semántica, orden por distancia y formato de salida.

```powershell
.\.venv\Scripts\python -m pytest -v
```

### Discusión

- **¿Por qué el hash?** Permite saber si un PDF bajado de nuevo reemplaza a uno
  ya indexado, sin borrar el índice completo.
- **¿Por qué retrieval puro?** La recuperación responde *"¿dónde está la
  información?"*; el LLM de la Fase 3 responde *"¿qué significa?"*. Separar las
  responsabilidades hace cada pieza testeable por su cuenta.
- **¿Por qué no indexar el PDF completo?** Un pliego puede tener cientos de
  páginas; la ventana de contexto del LLM es limitada. El retrieval reduce el
  universo a los fragmentos relevantes.

---

## 6. FASE 2 — Datos abiertos SECOP II (por construir)

**Objetivo:** consumir la API SODA de datos.gov.co para encontrar proveedores
con experiencia en contratación estatal.

### Ejercicios guiados

1. **Consulta SoQL.** Filtra por `objeto_del_contrato` y `departamento`.
2. **Limpieza.** Procesa campos numéricos (`valor_del_contrato`).
3. **Agrupación.** Calcula total de contratos y suma ejecutada por proveedor.
4. **Formato.** Retorna en Markdown o JSON para que el LLM lo consuma.

---

## 7. FASE 3 — Agente orquestador (por construir)

**Objetivo:** integrar RAG + datos abiertos en un agente LangChain propulsado
por NVIDIA Build API.

### El flujo del agente

1. El usuario hace una pregunta sobre la licitación.
2. El agente consulta `tool_rag_pliegos` para leer el pliego.
3. Con la información extraída, consulta `tool_secop_proveedores` en datos
   abiertos.
4. Responde de forma estructurada en español.

---

> **Aviso académico:** los datos de proveedores en el taller son de fuentes
> públicas (datos.gov.co). Los pliegos en `datos/pliegos/` son documentos
> públicos descargados de SECOP II. Nunca subas datos personales reales
> (Ley 1581 de 2012).
