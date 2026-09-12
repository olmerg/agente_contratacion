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
| 2    | Tool de datos abiertos (API SECOP II)           | ✅ Implementado|
| 3    | Agente orquestador con LangChain + NVIDIA       | ✅ Implementado|

---

## 2. Estructura del proyecto

```
agente_contratacion/
├── .env                     # API key de NVIDIA (NO se sube a Git)
├── .env-example             # Plantilla del .env
├── .gitignore
├── pyproject.toml           # Dependencias del proyecto
├── README.md                # Material para el estudiante
├── readme_rag.md            # Documentación técnica del RAG (para el agente de IA)
├── readme_secop.md          # Documentación técnica de la API SECOP II
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
>
> En `tests/data/secop_consulta_software.csv` hay una consulta real guardada
> para **mockear** la API en los tests sin volver a llamarla.

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

# 3. Ejecutar la fase que corresponda
.\.venv\Scripts\python src\fase0_smoke_test.py
.\.venv\Scripts\python src\fase1_rag_engine.py "cuales son las licencias del lote 1" --licitacion IDARTES-SA-SI-013-2026
.\.venv\Scripts\python src\fase2_secop_tools.py "software" --departamento "Bogotá DC"

# 4. Ejecutar el agente (Fase 3) - interactivo o con una pregunta
.\.venv\Scripts\python -m src.fase3_agent
.\.venv\Scripts\python -m src.fase3_agent "que licencias pide el Lote 2 del pliego IDARTES-SA-SI-013-2026?"

# 5. Ejecutar los tests unitarios (los de integracion son optativos: -m integracion)
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

Recupera de ChromaDB los fragmentos más relevantes de los pliegos ante una
pregunta. Es **retrieval puro (sin LLM)**: la extracción de datos complejos
(códigos UNSPSC, ítems, características técnicas) la hace el LLM de la Fase 3.

```powershell
# Si la licitación no está indexada, indexa su carpeta y responde la pregunta
.\.venv\Scripts\python src\fase1_rag_engine.py "cuales son las licencias del lote 1" --licitacion IDARTES-SA-SI-013-2026
```

> Documentación técnica completa (diseño, carga incremental, tests, discusión):
> ver **`readme_rag.md`**.

---

## 6. FASE 2 — Datos abiertos SECOP II (implementado)

**Objetivo:** consumir la API SODA de datos.gov.co (con el cliente oficial
`sodapy`) para encontrar proveedores con experiencia en contratación estatal.

```powershell
# Lista proveedores de 'software' en Bogotá, ordenados por total ejecutado
.\.venv\Scripts\python src\fase2_secop_tools.py "software" --departamento "Bogotá DC"

# Filtro adicional por categoría UNSPSC (código de categoria principal)
.\.venv\Scripts\python src\fase2_secop_tools.py "software" --departamento "Bogotá DC" --codigo-unspsc 48101501
```

Devuelve una tabla Markdown con proveedor, documento, número de contratos y
total ejecutado (es-CO: `$ 1.234.567`), lista para inyectarla a un LLM (Fase 3
la envolverá con `@tool`).

### Ejercicios guiados

1. **Consulta SoQL.** Filtra por `objeto_del_contrato` y `departamento`.
2. **Limpieza.** Procesa campos numéricos (`valor_del_contrato`).
3. **Agrupación.** Calcula total de contratos y suma ejecutada por proveedor.
4. **Formato.** Retorna en Markdown o JSON para que el LLM lo consuma.

> Documentación técnica (diseño, campos del dataset, estrategia de tests y
> mock con CSV): ver **`readme_secop.md`**.

---

## 7. FASE 3 — Agente orquestador (implementado)

**Objetivo:** integrar RAG + datos abiertos en un agente LangChain propulsado
por NVIDIA Build API. Se construye con `create_agent()` (la API recomendada de
LangChain 1.x, que arma un grafo de LangGraph por debajo), dos `@tool` y memoria
conversacional.

### El flujo del agente

1. El usuario hace una pregunta sobre la licitación.
2. El agente consulta `tool_rag_pliegos` para leer el pliego (Fase 1).
3. Con las palabras clave o códigos UNSPSC identificados, consulta
   `tool_secop_proveedores` en datos abiertos (Fase 2).
4. Responde de forma estructurada en español, citando fuente y página.

```powershell
# Modo interactivo (mantiene la conversación en sesión)
.\.venv\Scripts\python -m src.fase3_agent

# Una sola pregunta (modo uno-disparo)
.\.venv\Scripts\python -m src.fase3_agent "que licencias pide el Lote 2 del pliego IDARTES-SA-SI-013-2026?"

# Equivalentes instalados como comandos tras `pip install -e .`
secop-agent
```

El modelo se configura según su model card NVIDIA: se registra su perfil (tool
calling + soporte de thinking) y se desactiva el *reasoning* con
`chat_template_kwargs: {"enable_thinking": false}` para respuestas rápidas y
deterministas (`temperature=0`). Si tu clave de NVIDIA tiene otro modelo, cambia
`MODELO` en `src/fase3_agent.py`. Los tests de integración lanzan el agente por
**línea de comandos** (subproceso), tal como se usará en producción:
`pytest -m integracion tests\integration\test_fase3_agent_integracion.py`.

> **Nota:** sin `SECOP_APP_TOKEN` (opcional en `.env`) sodapy avisa que aplicará
> límites de tráfico a datos.gov.co; es un aviso, no un error.

---

> **Aviso académico:** los datos de proveedores en el taller son de fuentes
> públicas (datos.gov.co). Los pliegos en `datos/pliegos/` son documentos
> públicos descargados de SECOP II. Nunca subas datos personales reales
> (Ley 1581 de 2012).
