# Fase 2 — Datos Abiertos SECOP II (documentación técnica)

Referencia de `src/fase2_secop_tools.py` para quien mantiene el código (o para
el agente de IA que construya la Fase 3). El estudiante no necesita leerlo.

---

## 1. Diseño

La Fase 2 es una función-tool que consulta el dataset de contratos SECOP II y
devuelve una **tabla Markdown** de proveedores (contratos ganados + total
ejecutado) lista para inyectar a un LLM. Como el LLM la va a leer, **no se
pulen los datos**: se busca simple y claro.

Está pensada para envolverse en Fase 3 con `@tool`.

```python
buscar_proveedores_secop(termino_clave, departamento="Bogotá DC", codigo_unspsc=None) -> str
```

## 2. La librería: `sodapy`

Se usa el **cliente oficial** de la API SODA (la API de datos.gov.co):

```python
from sodapy import Socrata

cliente = Socrata("www.datos.gov.co", None)          # None = dataset público
filas = cliente.get(
    "jbjy-vk9h",
    where="objeto_del_contrato like '%software%'",
    limit=100,
)                                                   # -> list[dict] (JSON)
```

No hay HTTP manual: sodapy construye la URL, los parámetros SoQL y maneja los
errores. **Hallazgo verificado:** en este dataset los filtros implícitos
(`?objeto_del_contrato=LIKE '%x%'`) devuelven vacío; hay que usar **`where`**
(SoQL `$where`). El dep. en el dataset es "Distrito Capital de Bogotá": se
filtra local con la primera palabra del departamento pedido
(`str.contains("Bogotá")`) — suficiente para una tool del LLM.

## 3. Limpieza mínima

| Paso | Código |
| ---- | ------ |
| Montos | `pd.to_numeric(..., errors="coerce").fillna(0)` |
| Departamento | `df[df["departamento"].str.contains(primera_palabra, case=False)]` |
| Agrupar | `groupby(["proveedor_adjudicado", "documento_proveedor"])` → `count` + `sum` |
| Ordenar | por total ejecutado descendente |
| Formato | `"$ " + f"{int(total):,}".replace(",", ".")` (es-CO) |

## 4. Tests

```
tests/
├── test_fase2_secop_tools.py            # unit, sin red
├── data/secop_consulta_software.csv     # consulta real 'software' (445 filas)
└── integration/test_fase2_secop_integracion.py   # 1 llamada real
```

- Los **unit tests** reemplazan `Socrata` por un **cliente falso** que devuelve
  las filas del CSV fixture (`tests/data/secop_consulta_software.csv`,
  descargado **una sola vez** de la API). Correrlos no toca la red.
- El **test de integración** hace **una única** llamada real y está marcado
  `integracion` (se ejecuta aparte y se salta si la API falla).

`.\.venv\Scripts\python -m pytest -q`                  # sin red (mock del CSV)
`.\.venv\Scripts\python -m pytest -m integracion -q`   # Fases 1 y 2 con API/BD reales