"""Fase 2: Tooling de Datos Abiertos (API SECOP II / datos.gov.co).

Consulta el dataset jbjy-vk9h (contratos SECOP II) y devuelve, agrupado por
proveedor, cuantos contratos gano y cuanto suman, como tabla Markdown lista para
inyectar a un LLM (Fase 3 lo envolvera con @tool).

La funcion publica es buscar_proveedores_secop. El resto son ayudantes
testeables por separado.
"""

import argparse
import unicodedata

import pandas as pd
import requests

URL_API = "https://www.datos.gov.co/resource/jbjy-vk9h.json"
LIMITE_POR_CONSULTA = 100
DEPARTAMENTO_DEFECTO = "Bogotá DC"

# Columnas del dataset SECOP II (datos.gov.co, jbjy-vk9h)
CAMPO_OBJETO = "objeto_del_contrato"
CAMPO_DEPARTAMENTO = "departamento"
CAMPO_VALOR = "valor_del_contrato"
CAMPO_PROVEEDOR = "proveedor_adjudicado"
CAMPO_DOCUMENTO = "documento_proveedor"
CAMPO_UNSPSC = "codigo_de_categoria_principal"

# Palabras sin significado propio en un nombre de departamento
_DEPARTAMENTO_STOPWORDS = {
    "de", "del", "la", "las", "los", "y", "el", "al", "dc", "d.c.", "capital",
}

_MENSAJE_VACIO = "No se encontraron proveedores con experiencia en '{termino}' para {departamento}."


def _normalizar(texto) -> str:
    """Minusculas y sin acentos (para comparar departamentos con tolerancia)."""

    texto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").lower()


def _departamento_coincide(departamento_consulta: str, valor_bd) -> bool:
    """True si valor_bd corresponde al departamento consultado.

    Tolera variantes del dataset: 'Bogotá DC' == 'Distrito Capital de Bogotá'.
    Coincide si algun token significativo (>= 4 letras) de la consulta aparece
    en el valor guardado.
    """

    tokens = [
        t for t in _normalizar(departamento_consulta).split()
        if t not in _DEPARTAMENTO_STOPWORDS and len(t) >= 4
    ]
    if not tokens:
        return True
    valor = _normalizar(valor_bd)
    return any(t in valor for t in tokens)


def _limpiar_valor(valor) -> float:
    """Convierte un monto a float; tolera formato US (1,234.56) y ES (1.234,56)."""

    if valor is None:
        return 0.0
    s = str(valor).strip().replace("$", "").replace(" ", "").replace("\u00a0", "")
    if not s or s.upper() == "NAN":
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):   # formato español: 1.234.567,89
            s = s.replace(".", "").replace(",", ".")
        else:                             # formato inglés: 1,234,567.89
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "")
    elif "." in s and s.count(".") == 1 and len(s.rsplit(".", 1)[1]) == 3:
        s = s.replace(".", "")            # español sin decimales: 5.000 = 5000
    try:
        return float(s)
    except ValueError:
        return 0.0


def _construir_parametros(termino_clave: str, codigo_unspsc: str | None = None) -> dict:
    """Parametros SoQL para la API (filtro de objeto en el servidor)."""

    where = f"{CAMPO_OBJETO} like '%{termino_clave}%'"
    if codigo_unspsc:
        where += f" and {CAMPO_UNSPSC} = '{codigo_unspsc}'"
    return {"$where": where, "$limit": LIMITE_POR_CONSULTA}


def _consultar_api(parametros: dict) -> list[dict]:
    """Llamada HTTP a la API SECOP II. Punto de anclaje de los mocks en tests."""

    respuesta = requests.get(URL_API, params=parametros, timeout=60)
    respuesta.raise_for_status()
    return respuesta.json()


def _aplicar_filtros(
    filas: list[dict],
    termino_clave: str,
    departamento: str,
    codigo_unspsc: str | None,
) -> list[dict]:
    """Filtra en local; refuerza el like del servidor y filtra departamento."""

    termino = _normalizar(termino_clave)
    return [
        f
        for f in filas
        if termino in _normalizar(f.get(CAMPO_OBJETO, ""))
        and _departamento_coincide(departamento, f.get(CAMPO_DEPARTAMENTO, ""))
        and (
            codigo_unspsc is None
            or str(f.get(CAMPO_UNSPSC, "")) == codigo_unspsc
        )
    ]


def _agrupar_por_proveedor(filas: list[dict]) -> list[dict]:
    """Agrupa por proveedor/documento y calcula contratos y total ejecutado."""

    if not filas:
        return []

    df = pd.DataFrame(filas)
    df[CAMPO_VALOR] = df[CAMPO_VALOR].apply(_limpiar_valor)
    df[CAMPO_PROVEEDOR] = df[CAMPO_PROVEEDOR].fillna("No identificado")
    df[CAMPO_DOCUMENTO] = df[CAMPO_DOCUMENTO].fillna("")

    agrupado = (
        df.groupby([CAMPO_PROVEEDOR, CAMPO_DOCUMENTO], dropna=False)
        .agg(
            contratos=(CAMPO_VALOR, "size"),
            total_ejecutado=(CAMPO_VALOR, "sum"),
        )
        .reset_index()
        .sort_values("total_ejecutado", ascending=False)
    )

    return [
        {
            "proveedor": fila[CAMPO_PROVEEDOR],
            "documento": fila[CAMPO_DOCUMENTO],
            "contratos": int(fila["contratos"]),
            "total_ejecutado": float(fila["total_ejecutado"]),
        }
        for _, fila in agrupado.iterrows()
    ]


def _formatear_dinero(valor: float) -> str:
    """Monto en formato es-CO: $ 1.234.567"""

    return "$ " + f"{int(round(valor)):,}".replace(",", ".")


def _formatear_markdown(agrupados: list[dict], termino_clave: str, departamento: str, contratos: int) -> str:
    """Tabla Markdown con los proveedores, ordenados por total ejecutado."""

    if not agrupados:
        return _MENSAJE_VACIO.format(termino=termino_clave, departamento=departamento)

    encabezado = (
        f"Proveedores con experiencia en '{termino_clave}' en {departamento} "
        f"({len(agrupados)} proveedores, {contratos} contratos coincidentes)\n\n"
    )
    tabla = "| # | Proveedor | Documento | Contratos | Total ejecutado |\n|---|---|---|---|---|\n"
    for i, r in enumerate(agrupados, 1):
        proveedor = r["proveedor"].replace("|", "/")
        documento = r["documento"].replace("|", "/")
        tabla += (
            f"| {i} | {proveedor} | {documento} | {r['contratos']} "
            f"| {_formatear_dinero(r['total_ejecutado'])} |\n"
        )
    return encabezado + tabla


def buscar_proveedores_secop(
    termino_clave: str,
    departamento: str = DEPARTAMENTO_DEFECTO,
    codigo_unspsc: str | None = None,
) -> str:
    """Busca proveedores en la API de SECOP II y devuelve una tabla Markdown."""

    parametros = _construir_parametros(termino_clave, codigo_unspsc)
    filas = _consultar_api(parametros)
    filas = _aplicar_filtros(filas, termino_clave, departamento, codigo_unspsc)
    agrupados = _agrupar_por_proveedor(filas)
    return _formatear_markdown(agrupados, termino_clave, departamento, len(filas))


def main_cli() -> None:
    parser = argparse.ArgumentParser(
        description="Consulta proveedores en la API SECOP II (datos.gov.co)"
    )
    parser.add_argument("termino_clave", help="Texto a buscar en objeto_del_contrato")
    parser.add_argument("--departamento", default=DEPARTAMENTO_DEFECTO)
    parser.add_argument("--codigo-unspsc", default=None, dest="codigo_unspsc")
    args = parser.parse_args()

    try:
        print(
            buscar_proveedores_secop(
                args.termino_clave, args.departamento, args.codigo_unspsc
            )
        )
    except requests.RequestException as e:
        raise SystemExit(f"Error consultando la API de SECOP II: {e}")


if __name__ == "__main__":
    main_cli()