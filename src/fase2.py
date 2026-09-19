"""Fase 2: Herramientas de Datos Abiertos (API SECOP II)

Objetivo:
Consumir la API SODA de Datos Abiertos Colombia (datos.gov.co, dataset jbjy-vk9h)
para consultar contratos previos y consolidar proveedores con experiencia
según término de búsqueda, departamento y categoría UNSPSC.
"""

import argparse
import os
from typing import Optional
import pandas as pd
from dotenv import load_dotenv
from sodapy import Socrata

# ---------------------------------------------------------
# Configuración y Constantes
# ---------------------------------------------------------


DOMINIO_DATOS_GOV = "www.datos.gov.co"
DATASET_SECOP_CONTRATOS = "jbjy-vk9h"


# ---------------------------------------------------------
# Funciones Principales
# ---------------------------------------------------------

def construir_consulta_soql(
    termino_clave: str,
    departamento: Optional[str] = "Bogotá DC",
    codigo_unspsc: Optional[str] = None,
) -> str:
    """Construye la cláusula WHERE en SoQL con sanitización básica."""
    termino_limpio = termino_clave.strip().replace("'", "''")
    condiciones = [f"lower(objeto_del_contrato) like '%{termino_limpio.lower()}%'"]

    if departamento and departamento.strip():
        depto_limpio = departamento.strip().replace("'", "''")
        condiciones.append(f"departamento = '{depto_limpio}'")

    if codigo_unspsc and codigo_unspsc.strip():
        unspsc_limpio = codigo_unspsc.strip().replace("'", "''")
        condiciones.append(f"codigo_de_categoria_principal = '{unspsc_limpio}'")

    return " AND ".join(condiciones)


def procesar_y_agrupar_proveedores(registros: list[dict]) -> pd.DataFrame:
    """Limpia tipos de datos y agrupa contratos por proveedor."""
    if not registros:
        return pd.DataFrame()

    df = pd.DataFrame(registros)

    # Asegurar existencia de columnas necesarias
    for col in ["proveedor_adjudicado", "documento_proveedor", "valor_del_contrato"]:
        if col not in df.columns:
            df[col] = "No Registrado" if col != "valor_del_contrato" else 0

    # Limpieza y conversión de tipos
    df["proveedor_adjudicado"] = df["proveedor_adjudicado"].fillna("No Registrado").astype(str).str.strip()
    df["documento_proveedor"] = df["documento_proveedor"].fillna("No Registrado").astype(str).str.strip()
    df["valor_del_contrato"] = pd.to_numeric(df["valor_del_contrato"], errors="coerce").fillna(0)

    # Agrupación y cálculo de métricas
    df_agrupado = (
        df.groupby(["proveedor_adjudicado", "documento_proveedor"], as_index=False)
        .agg(
            total_contratos=("valor_del_contrato", "count"),
            total_ejecutado=("valor_del_contrato", "sum"),
        )
        .sort_values(by=["total_ejecutado", "total_contratos"], ascending=[False, False])
    )

    return df_agrupado


def formatear_tabla_proveedores(
    df_proveedores: pd.DataFrame,
    termino_clave: str,
    departamento: Optional[str],
    codigo_unspsc: Optional[str],
    total_registros: int,
) -> str:
    """Convierte el DataFrame consolidado en una tabla Markdown legible para el LLM."""
    if df_proveedores.empty:
        return "No se encontraron proveedores que coincidan con los criterios."

    md = (
        f"### Proveedores con experiencia en SECOP II\n"
        f"- **Término clave:** `{termino_clave}`\n"
        f"- **Departamento:** `{departamento or 'Todos'}`\n"
    )
    if codigo_unspsc:
        md += f"- **Categoría UNSPSC:** `{codigo_unspsc}`\n"

    md += (
        f"- **Total contratos analizados:** {total_registros}\n\n"
        f"| # | Proveedor Adjudicado | Documento / NIT | # Contratos | Total Ejecutado (COP) |\n"
        f"|---|---|---|---|---|\n"
    )

    for idx, row in enumerate(df_proveedores.itertuples(), start=1):
        valor_formateado = f"${row.total_ejecutado:,.0f}".replace(",", ".")
        md += (
            f"| {idx} | {row.proveedor_adjudicado} | {row.documento_proveedor} | "
            f"{row.total_contratos} | {valor_formateado} |\n"
        )

    return md


def buscar_proveedores_secop(
    termino_clave: str,
    departamento: Optional[str] = "Bogotá DC",
    codigo_unspsc: Optional[str] = None,
    limite: int = 1000,
) -> str:
    """Función principal (contrato del taller): Consulta la API y retorna la tabla en Markdown."""
    if not termino_clave or not termino_clave.strip():
        return "Debe proporcionar un término clave válido para realizar la búsqueda."

    app_token = os.getenv("SECOP_APP_TOKEN")
    client = Socrata(DOMINIO_DATOS_GOV, app_token=app_token, timeout=30)

    where_clause = construir_consulta_soql(
        termino_clave=termino_clave,
        departamento=departamento,
        codigo_unspsc=codigo_unspsc,
    )

    try:
        registros = client.get(
            DATASET_SECOP_CONTRATOS,
            where=where_clause,
            limit=limite,
        )
    except Exception as error:
        return f"Error al consultar la API de SECOP II: {error}"
    finally:
        client.close()

    if not registros:
        msg = f"No se encontraron contratos para el término '{termino_clave}'"
        if departamento:
            msg += f" en el departamento '{departamento}'"
        if codigo_unspsc:
            msg += f" con código UNSPSC '{codigo_unspsc}'"
        return msg + "."

    df_agrupado = procesar_y_agrupar_proveedores(registros)

    return formatear_tabla_proveedores(
        df_proveedores=df_agrupado,
        termino_clave=termino_clave,
        departamento=departamento,
        codigo_unspsc=codigo_unspsc,
        total_registros=len(registros),
    )


# ---------------------------------------------------------
# Interfaz de Línea de Comandos (CLI)
# ---------------------------------------------------------

def main_cli():
    parser = argparse.ArgumentParser(
        description="Buscar y agregar proveedores con experiencia en SECOP II (datos.gov.co)."
    )
    parser.add_argument(
        "termino_clave",
        help="Término clave a buscar en el objeto del contrato (ej. 'software', 'licencias').",
    )
    parser.add_argument(
        "--departamento",
        default="Bogotá DC",
        help="Departamento para filtrar la búsqueda (por defecto: 'Bogotá DC').",
    )
    parser.add_argument(
        "--codigo-unspsc",
        dest="codigo_unspsc",
        default=None,
        help="Código de categoría principal UNSPSC.",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=100,
        help="Número máximo de registros a descargar de la API (por defecto: 1000).",
    )
    load_dotenv()

    args = parser.parse_args()

    print(f"Consultando SECOP II para '{args.termino_clave}'...")
    resultado = buscar_proveedores_secop(
        termino_clave=args.termino_clave,
        departamento=args.departamento,
        codigo_unspsc=args.codigo_unspsc,
        limite=args.limite,
    )
    print("\n" + resultado)


if __name__ == "__main__":
    main_cli()

