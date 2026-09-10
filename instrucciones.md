
Guía de Proyecto: Asistente Inteligente de Contratación Estatal (SECOP II)

Este proyecto busca construir un agente conversacional autónomo para el análisis de licitaciones públicas en Colombia, divido en 4 fases incrementales (Fase 0 a Fase 3).🏗️ Arquitectura Generalsecop-agent/
├── .env (nunca lo debe leer el agente de codigo ni git)

├── .env-example
├── pyproject.toml
├── README.md
├── datos/
│   └── pliegos/             # PDFs descargados de SECOP II
├── chroma_db/               # Base de datos vectorial persistente
└── src/
    ├── __init__.py
    ├── fase0_smoke_test.py  # Hola mundo Chroma
    ├── fase1_rag_engine.py  # Ingesta y retrieval con ChromaDB
    ├── fase2_secop_tools.py # Integración con API SODA datos.gov.co
    └── fase3_agent.py       # Agente LangChain + NVIDIA Build API
🛠️ Stack TecnológicoGestor de paquetes: uv (o pip)Vector DB: chromadbOrquestador: langchain / langchain-communityLLM Provider: NVIDIA Build API (langchain-nvidia-ai-endpoints)Embeddings: langchain-community con HuggingFace / BAAI (bge-m3) o OpenAIConsumo API: requests, pandas⚙️ Configuración del Entorno (pyproject.toml)[project]
name = "secop-ai-agent"
version = "0.1.0"
description = "Agente de IA para Inteligencia de Mercado en Contratación Estatal Colombiana"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "chromadb>=0.4.24",
    "langchain>=0.2.0",
    "langchain-community>=0.2.0",
    "langchain-nvidia-ai-endpoints>=0.1.0",
    "pypdf>=4.0.0",
    "pandas>=2.0.0",
    "requests>=2.31.0",
    "python-dotenv>=1.0.0",
    "sentence-transformers>=2.7.0"
]
Configuración de Variables de Entorno (.env)NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxxxxxx

# De manera alternativa si usan embeddings de OpenAI:

# OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx

🚀 FASES DEL PROYECTOFASE 0: Inicialización y Smoke TestObjetivo: Verificar la instalación de dependencias y el correcto funcionamiento de ChromaDB en entorno local.Crear el entorno con uv:uv venv
source .venv/bin/activate  # En Linux/macOS
uv pip install -e .
Implementar src/fase0_smoke_test.py:Crear un cliente efímero o persistente de Chroma.Insertar 2 documentos simples de prueba.Ejecutar una consulta de prueba e imprimir la respuesta.FASE 1: Motor RAG sobre Pliegos Licitatorios (ChromaDB)Objetivo: Crear un módulo modular que procese PDFs de pliegos técnicos (datos/pliegos/), los divida en chunks, genere embeddings y responda preguntas semánticas.Especificación para src/fase1_rag_engine.py:Crear una clase o función PliegoRAG:Método cargar_e_indexar(folder_path: str):Usa PyPDFDirectoryLoader para leer todos los PDFs de datos/pliegos/.Usa RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200).Guarda los vectores en ./chroma_db de forma persistente.Método consultar_pliego(query: str, k: int = 3):Recupera los k contextos más relevantes.Retorna el texto consolidado junto con la fuente (metadata del PDF).FASE 2: Tooling de Datos Abiertos (API SECOP II)Objetivo: Construir un módulo independiente que consuma el API SODA de Datos Abiertos Colombia (datos.gov.co, dataset jbjy-vk9h) y retorne métricas agregadas de proveedores.Especificación para src/fase2_secop_tools.py:Crear una función buscar_proveedores_secop(termino_clave: str, departamento: str = "Bogotá DC", codigo_unspsc: str = None) -> str:Construir una consulta SoQL a https://www.datos.gov.co/resource/jbjy-vk9h.json.Filtrar por objeto_del_contrato usando el operador LIKE '%{termino_clave}%'.Filtrar por departamento.Limpiar campos numéricos (valor_del_contrato).Agrupar por proveedor_adjudicado y documento_proveedor.Calcular: Total de contratos ganados y Suma total ejecutada.Retornar el resultado en formato Markdown o JSON para el LLM.FASE 3: Agente Orquestador con LangChain y NVIDIA Build APIObjetivo: Integrar el motor RAG de la Fase 1 y la herramienta de la API de la Fase 2 en un Agente autónomo propulsado por NVIDIA Build API (ChatNVIDIA).Especificación para src/fase3_agent.py:Configurar el LLM:from langchain_nvidia_ai_endpoints import ChatNVIDIA

llm = ChatNVIDIA(model="meta/llama-3.1-70b-instruct")
2. Envolver las funciones de las Fases 1 y 2 en herramientas de LangChain usando la anotación `@tool`:

- `tool_rag_pliegos`: Permite al agente consultar especificaciones, lotes y requisitos técnicos del PDF.
- `tool_secop_proveedores`: Permite consultar antecedentes de contratistas en la API pública.

3. Crear el agente de llamadas a herramientas (*Tool Calling Agent* / *LangGraph*):
   - Definir un prompt de sistema que le indique al agente: *"Eres un consultor experto en contratación estatal colombiana. Para responder la duda del usuario, primero debes consultar las condiciones técnicas del pliego cargado con `tool_rag_pliegos`. Luego, utiliza las palabras clave o códigos identificados para buscar los proveedores con mayor experiencia en `tool_secop_proveedores`."*
4. Exponer una interfaz de consola interactiva para el usuario final.

---

## 🧪 Ejemplo de Evaluación / Prueba de Integración

Ejecutar en la terminal:

```bash
python -m src.fase3_agent
Pregunta del evaluador:"Revisa el anexo técnico cargado y dime qué licencias se solicitan para el Lote 2. Con base en eso, busca en Datos Abiertos qué proveedores han entregado ese tipo de software en Bogotá y ordénalos por valor contratado."Resultado esperado:El agente debe realizar 2 ejecuciones automáticas de herramientas (Tool Calls) y responder de manera estructurada en español.
```
