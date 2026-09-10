# Fase 2 — Datos Abiertos SECOP II (documentación técnica)

Documento de referencia del módulo `src/fase2_secop_tools.py`. Pensado para
quien mantiene el código (o para el agente de IA que construya la Fase 3 sobre
esta base). El estudiante no necesita leerlo.

---

## 1. Diseño

La Fase 2 es una **herramienta (tool)** que consulta el dataset abierto de
contratos de SECOP II en datos.gov.co y devuelve, agrupado por proveedor,
cuántos contratos ganó y cuánto suman. Su salida es **texto Markdown** listo
para inyectar a un LLM (Fase 3 la envolverá con `@tool`).

```python
buscar_proveedores_secop(termino_clave, departamento="Bogotá DC", codigo_unspsc=None) -> str
└── _construir_parametros(...)    # SoQL (filtro de objeto en el servidor)
└── _consultar_api(parametros)    # HTTP a la API  <-- punto de anclaje de los mocks
└── _aplicar_filtros(...)         # filtro local (departamento tolerante, UNSPSC)
└── _agrupar_por_proveedor(...)   # pandas: contratos y total ejecutado por proveedor
└── _formatear_markdown(...)      # tabla Markdown ordenada por total (es-CO)
```

## 2. La API real

- **Endpoint:** `https://www.datos.gov.co/resource/jbjy-vk9h.json` (dataset
  SECOP II, [datos.gov.co](https://www.datos.gov.co), columna de formatos en
  SODA). El export `.csv` del mismo dataset es el de los fixtures.
- **Sintaxis y hallazgos verificados:**
  - Los filtros **implícitos** de SODA (`?objeto_del_contrato=LIKE '%x%'`)
    **no devuelven nada** en este dataset; hay que usar **`$where`**:
    `objeto_del_contrato like '%x%'`.
  - El departamento en el dataset es **"Distrito Capital de Bogotá"**, no
    "Bogotá DC". Por eso el departamento **no se filtra en el servidor**, sino
    en local con normalización (quitar acentos, minúsculas) y coincidencia por
    token significativo: `"Bogotá DC"` == `"Distrito Capital de Bogotá"`.
  - La cláusula `$where` se limita a **100 filas** (`$limit`) para que las
    llamadas sean ligeras y la consulta no se bloquee.

## 3. Campos usados del dataset

| Campo en el código | Campo en el dataset          |
| ------------------ | ---------------------------- |
| `CAMPO_OBJETO`     | `objeto_del_contrato`        |
| `CAMPO_DEPARTAMENTO`| `departamento`              |
| `CAMPO_VALOR`      | `valor_del_contrato`         |
| `CAMPO_PROVEEDOR`  | `proveedor_adjudicado`       |
| `CAMPO_DOCUMENTO`  | `documento_proveedor`        |
| `CAMPO_UNSPSC`     | `codigo_de_categoria_principal` |

### Limpieza de montos

`valor_del_contrato` llega como **string** (en el CSV a veces sin separadores).
`_limpiar_valor` tolera: `"1.234.567"`, `"1,234,567.89"`, `"$ 5.000"`, `"NaN"`,
`None`. La regla para el punto como millar (es-CO): solo cuando hay **un** punto
con **3 dígitos** después; si no, es decimal.

### Agrupación

`_agrupar_por_proveedor` usa `pandas` (`groupby` por proveedor + documento):
`contratos` = número de filas (cada fila es un contrato), `total_ejecutado` =
suma de `valor_del_contrato` limpio. Se ordena por total descendente.

## 4. Fixture CSV para mockear la API

Se autoriza **una sola** descarga real de la API por consulta, para no saturar
ni exponernos a bloqueos. Esa respuesta se guarda en
`tests/data/secop_consulta_software.csv` (445 filas reales del export `.csv` de
la consulta `objeto like '%software%'`, `$limit=100`).

- Los **unit tests** `monkeypatch` a `_consultar_api` (el único punto que toca
  la red) para que lea el CSV; así la suite normal corre **sin llamadas HTTP**.
- La **prueba de integración** es exactamente **una** llamada real a la API y
  está marcada `integracion`; se ejecuta aparte (`pytest -m integracion`) y se
  omite automáticamente si la API está caída.

## 5. Tests

```
tests/
├── test_fase2_secop_tools.py            # unit tests (mock del CSV), rápidos
├── data/
│   └── secop_consulta_software.csv      # fixture real (consulta descargada una vez)
└── integration/
    └── test_fase2_secop_integracion.py  # una llamada real a la API
```

`.\.venv\Scripts\python -m pytest -q`          # sin red (usa el CSV)
`.\.venv\Scripts\python -m pytest -m integracion -q`   # Fases 1 y 2 reales