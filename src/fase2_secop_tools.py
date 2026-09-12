"""Fase 2: Datos Abiertos SECOP II con sodapy (cliente oficial de SODA).

`buscar_proveedores_secop` consulta el dataset jbjy-vk9h de datos.gov.co y
devuelve, como tabla Markdown, los proveedores con contratos sobre un termino.
La salida la va a leer un LLM (Fase 3), asi que no pulimos los datos.
"""

import os

import pandas as pd
from sodapy import Socrata

DOMINIO = "www.datos.gov.co"
DATASET_ID = "jbjy-vk9h"


def _cliente_soda() -> Socrata:
    """Cliente de datos.gov.co.

    SECOP_APP_TOKEN es opcional: sin el, sodapy registra un aviso de limites
    de trafico pero no falla. Llama a load_dotenv() antes de importar este
    modulo si necesitas el token desde un archivo .env.
    """
    return Socrata(DOMINIO, None, app_token=os.getenv("SECOP_APP_TOKEN"))


def buscar_proveedores_secop(
    termino_clave: str,
    departamento: str = "Bogotá DC",
    codigo_unspsc: str | None = None,
) -> str:
    """Busca proveedores en SECOP II y devuelve una tabla Markdown."""

    cliente = _cliente_soda()

    # NOTA: termino_clave no se sanitiza — aceptable en taller pero
    # en produccion habria que escapar comillas simples para evitar
    # inyeccion SoQL (ej: "soft' OR '1'='1")
    termino_seguro = termino_clave.replace("'", "")
    where = f"objeto_del_contrato like '%{termino_seguro}%'"
    if codigo_unspsc:
        where += f" and codigo_de_categoria_principal = '{codigo_unspsc}'"

    filas = cliente.get(DATASET_ID, where=where, limit=100)

    df = pd.DataFrame(filas)
    if df.empty:
        return f"No se encontraron contratos con '{termino_clave}' en {departamento}."

    # El dataset guarda 'Distrito Capital de Bogotá'; con la primera palabra
    # del departamento pedido alcanza (Bogotá, Antioquia, Valle, ...)
    primera_palabra = departamento.split()[0]
    df = df[df["departamento"].str.contains(primera_palabra, case=False)]

    df["valor"] = pd.to_numeric(df["valor_del_contrato"], errors="coerce").fillna(0)
    resumen = (
        df.groupby(["proveedor_adjudicado", "documento_proveedor"], dropna=False)["valor"]
        .agg(contratos="count", total_ejecutado="sum")
        .sort_values("total_ejecutado", ascending=False)
        .reset_index()
    )

    if resumen.empty:
        return f"No se encontraron contratos con '{termino_clave}' en {departamento}."

    tabla = "| # | Proveedor | Documento | Contratos | Total ejecutado |\n|---|---|---|---|---|\n"
    # MEJORA: enumerate sobre itertuples() es mas Pythonico y evita depender
    # del indice del DataFrame (que reset_index() ya normaliza, pero es fragil)
    for num, fila in enumerate(resumen.itertuples(index=False), 1):
        total = "$ " + f"{int(fila.total_ejecutado):,}".replace(",", ".")
        tabla += (
            f"| {num} | {fila.proveedor_adjudicado} | {fila.documento_proveedor} "
            f"| {fila.contratos} | {total} |\n"
        )
    return f"Proveedores con experiencia en '{termino_clave}' en {departamento}:\n\n{tabla}"


def main_cli() -> None:
    import argparse

    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Consulta proveedores en la API SECOP II (datos.gov.co)"
    )
    parser.add_argument("termino_clave", help="Texto a buscar en objeto_del_contrato")
    parser.add_argument("--departamento", default="Bogotá DC")
    parser.add_argument("--codigo-unspsc", default=None, dest="codigo_unspsc")
    args = parser.parse_args()

    # Sin try/except: si la API falla, el error completo es más util que un
    # mensaje generico. Fail-fast: el estudiante ve exactamente que salio mal.
    print(
        buscar_proveedores_secop(
            args.termino_clave, args.departamento, args.codigo_unspsc
        )
    )


if __name__ == "__main__":
    main_cli()