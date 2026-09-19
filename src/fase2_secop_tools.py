"""Fase 2: Datos Abiertos SECOP II con sodapy (cliente oficial de SODA).

`buscar_proveedores_secop` consulta el dataset jbjy-vk9h de datos.gov.co y
devuelve, como tabla Markdown, los proveedores con contratos sobre un termino.
La salida la va a leer un LLM (Fase 3), asi que no pulimos los datos.
"""

import pandas as pd
from sodapy import Socrata

DOMINIO = "www.datos.gov.co"
DATASET_ID = "jbjy-vk9h"


def buscar_proveedores_secop(
    termino_clave: str,
    departamento: str = "Bogotá DC",
    codigo_unspsc: str | None = None,
    timeout: int = 60,
) -> str:
    """Busca proveedores en SECOP II y devuelve una tabla Markdown."""

    cliente = Socrata(DOMINIO, None, timeout=timeout)

    where = f"objeto_del_contrato like '%{termino_clave}%'"
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
    for i, fila in resumen.iterrows():
        total = "$ " + f"{int(fila['total_ejecutado']):,}".replace(",", ".")
        tabla += (
            f"| {i + 1} | {fila['proveedor_adjudicado']} | {fila['documento_proveedor']} "
            f"| {fila['contratos']} | {total} |\n"
        )
    return f"Proveedores con experiencia en '{termino_clave}' en {departamento}:\n\n{tabla}"


def main_cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Consulta proveedores en la API SECOP II (datos.gov.co)"
    )
    parser.add_argument("termino_clave", help="Texto a buscar en objeto_del_contrato")
    parser.add_argument("--departamento", default="Bogotá DC")
    parser.add_argument("--codigo-unspsc", default=None, dest="codigo_unspsc")
    args = parser.parse_args()

    try:
        print(
            buscar_proveedores_secop(
                args.termino_clave, args.departamento, args.codigo_unspsc
            )
        )
    except Exception as e:
        raise SystemExit(f"Error consultando la API de SECOP II: {e}")


if __name__ == "__main__":
    main_cli()