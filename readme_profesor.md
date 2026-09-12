# Guía del Profesor — Taller Agente SECOP II

> Revisión pedagógica generada en branch `fase-p`. Dirigida al docente, no al
> estudiante. Contiene observaciones sobre el código entregado como punto de
> partida (main) y recomendaciones de mejora aplicadas en este branch.

---

## 1. Evaluación general del objetivo

El taller está bien planteado: cuatro fases incrementales que llevan al
estudiante desde "ChromaDB funciona" hasta "un agente real responde preguntas
sobre contratos públicos". El problema de dominio (SECOP II) es concreto,
verificable con datos públicos y relevante para Colombia. ✅

### Fortalezas del diseño original

| Aspecto | Detalle |
|---------|---------|
| Progresión incremental | Cada fase tiene salida observable antes de pasar a la siguiente |
| Fail-fast en el agente | `crear_agente()` falla de inmediato si falta `NVIDIA_API_KEY` |
| Tests de IA sin sobrecarga al estudiante | Mock de red (CSV fixture) y monkeypatching; el estudiante no los implementa |
| Separación de responsabilidades | RAG, API SECOP y orquestación en módulos independientes |
| CLI directo y ejecutable | Cada fase se puede correr en una línea |

---

## 2. Problemas detectados y recomendaciones

### 2.1 Fase 0 — Smoke test

**Problema leve:** El emoji `✅` del mensaje final fue reemplazado por `[OK]`
en el código real (diferente a lo que documenta el README). Es una inconsistencia
menor pero confunde al estudiante que verifica contra la salida esperada.

**Recomendación:** Restaurar el `✅` o actualizar el README. Aplicado en este
branch.

---

### 2.2 Fase 1 — Motor RAG

**Problema 1 — Acceso a API privada de ChromaDB:**
```python
# ANTES (frágil, usa API interna _collection)
ids_actuales = self.vectorstore._collection.get()["ids"]
self.vectorstore._collection.delete(ids=ids_actuales)

# TAMBIÉN
return self.vectorstore._collection.count() > 0
```
El prefijo `_` indica API privada. ChromaDB puede cambiarla entre versiones sin
aviso. El estudiante hereda este patrón y lo replica.

**Recomendación:** Usar la API pública de LangChain-Chroma. Aplicado en este
branch mediante `get()` en la colección a través de la propiedad pública.

**Problema 2 — `indexar` borra y re-indexa siempre:** Si el estudiante llama
`indexar` dos veces seguidas, la segunda borra lo que recién hizo. No hay
mensaje de advertencia. Esto provoca confusión en el taller cuando los chunks
"desaparecen".

**Recomendación:** Emitir un `print` de advertencia cuando se detecta una base
ya poblada y se va a sobrescribir. Bajo impacto, alta visibilidad pedagógica.

**Problema 3 — `main_cli` usa `raise SystemExit` indirectamente:** Al no
existir la carpeta de la licitación, el error es claro. Correcto. ✅

---

### 2.3 Fase 2 — Datos abiertos SECOP

**Problema 1 — Inyección SoQL (SQL injection ligera):**
```python
where = f"objeto_del_contrato like '%{termino_clave}%'"
```
Si el estudiante pasa `software' OR '1'='1`, la consulta se rompe o devuelve
todo. En un taller académico es aceptable, pero conviene mencionarlo como
deuda técnica con un comentario explícito para que el estudiante lo vea.

**Recomendación:** Añadir comentario `# NOTA: sin sanitizar — aceptable en taller`
y sanitizar quitando comillas simples del término. Aplicado.

**Problema 2 — `resumen.iterrows()` con índice `i` no reiniciado:**
```python
for i, fila in resumen.iterrows():
    tabla += f"| {i + 1} | ..."
```
`iterrows()` conserva el índice del DataFrame original. Tras `reset_index()` el
índice sí va de 0 a N, pero si en el futuro alguien quita el `reset_index()`,
los números de fila quedan mal. Además, `enumerate` es más Pythónico y explícito.

**Recomendación:** Usar `enumerate(resumen.itertuples(), 1)`. Aplicado.

**Problema 3 — `load_dotenv()` dentro de `main_cli` pero no en `buscar_proveedores_secop`:**
La función de negocio depende de `SECOP_APP_TOKEN` en el entorno, pero no
documenta que `load_dotenv()` debe haberse llamado antes. Si el estudiante
importa `buscar_proveedores_secop` directamente, el token no se carga.

**Recomendación:** Mover el comentario de `SECOP_APP_TOKEN` a la función
`_cliente_soda` (ya está en el docstring). No se mueve `load_dotenv` al módulo
para no contaminar importaciones en Fase 3. El docstring actualizado aclara
el contrato. Aplicado.

---

### 2.4 Fase 3 — Agente orquestador

**Problema 1 — Excepción genérica en el loop interactivo:**
```python
except Exception as e:
    print(f"Error procesando la pregunta: {e}")
```
Esto atrapa **cualquier** error, incluyendo `KeyboardInterrupt` o errores de red
fatales. El estudiante no ve el traceback y no sabe qué falló. Es un fusible
que oculta el problema.

**Recomendación:** Capturar solo `Exception` y relanzar si es teclado; y en
modo *no interactivo* no usar try/except para que los errores sean visibles.
Aplicado: el modo interactivo mantiene el `except` pero imprime el tipo de
error para diagnóstico rápido.

**Problema 2 — `_registrar_perfil_modelo` es magia invisible:**
Esta función registra el modelo en el catálogo estático de `langchain-nvidia`
usando una clave interna `MODEL_TABLE`. Si el paquete cambia la estructura,
falla silenciosamente o con un error críptico. El estudiante no entiende por
qué existe.

**Recomendación:** Añadir un comentario de contexto que explique el "por qué"
(el modelo es nuevo y aún no está en el catálogo del paquete). Aplicado.

**Problema 3 — `agente.nodes["tools"]` en el test:**
```python
tools = agente.nodes["tools"].bound.tools_by_name
```
Accede a la estructura interna de LangGraph. Si LangGraph cambia los nombres
de nodos, el test falla sin que el agente esté roto. No es problema del
estudiante (el test es para la IA), pero sí es deuda técnica.

**Recomendación:** Documentado en el archivo de tests. No se cambia
(los tests son para la IA).

---

## 3. Filosofía de las mejoras aplicadas en `fase-p`

Las mejoras siguen tres principios:

1. **Fallar rápido y con mensaje claro.** Ningún error se silencia sin un
   mensaje que diga qué falló y qué hacer. Los `try/except` genéricos que
   ocultan stacktraces son removidos o acotados.

2. **Sin software fusible.** No se añaden capas de reintento, fallback ni
   "modo degradado" que hagan que el código "funcione" aunque algo esté roto.
   Si falta una dependencia, el programa termina con un error claro.

3. **Comentarios breves y dirigidos al estudiante.** Cada mejora lleva un
   comentario de una línea que explica el "por qué", no el "qué". El código
   debe ser auto-explicativo para un estudiante de postgrado.

---

## 4. Lo que NO se cambia (y por qué)

| Elemento | Razón para mantenerlo |
|----------|----------------------|
| `EmbeddingFunction` (adaptador manual) | Pedagógico: muestra cómo envolver una dependencia externa |
| `PliegoRAG` como clase | El estado (licitación, directorio) es cohesivo con la clase |
| `MemorySaver` en el agente | Memoria conversacional simple, correcta para el taller |
| Tests con monkeypatch de `Socrata` | Patrón correcto de mock de red sin dependencias externas |
| `RECURSION_LIMIT = 12` | Protección razonable contra loops infinitos del agente |
| Fixture CSV para tests de Fase 2 | Mejor práctica: snapshot de datos reales para reproducibilidad |

---

## 5. Sugerencias para el taller en clase

1. **Antes de la Fase 1:** mostrar qué es un embedding con la Fase 0 en vivo.
   Preguntar: *"¿qué pasa si cambio 'licencias de software' por 'contratos de servicios'?"*

2. **Fase 2 en clase:** ejecutar con `--codigo-unspsc 48101501` (software) vs
   sin ese filtro. Discutir por qué hay diferencia en los resultados.

3. **Fase 3:** pedir al estudiante que cambie el `system_prompt` para que el
   agente responda en inglés o en formato JSON. Observar cómo cambia el
   comportamiento sin tocar las tools.

4. **Evaluación sugerida:** que el estudiante agregue una tercera tool
   (`tool_buscar_licitacion_por_municipio`) siguiendo el mismo patrón de `@tool`
   de la Fase 3.

5. **Trampa pedagógica útil:** borrar la carpeta `chroma_db/` entre sesiones
   para que el estudiante observe la re-indexación y entienda la persistencia.

