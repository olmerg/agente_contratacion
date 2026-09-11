"""Fase 3: Agente orquestador (LangChain + NVIDIA Build API).

Une el RAG de pliegos (Fase 1) y la busqueda de proveedores (Fase 2) en un
agente que responde preguntas sobre licitaciones, decidiendo que tool usar.
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_nvidia_ai_endpoints import ChatNVIDIA, Model
from langchain_nvidia_ai_endpoints._statics import MODEL_TABLE
from langgraph.checkpoint.memory import MemorySaver

from src.fase1_rag_engine import PliegoRAG, formatear_resultados
from src.fase2_secop_tools import buscar_proveedores_secop

load_dotenv()  # carga NVIDIA_API_KEY desde el .env (sin leerlo)

MODELO = "nvidia/nemotron-3.5-lightning-30b-a3b"
RECURSION_LIMIT = 12


def _registrar_perfil_modelo() -> None:
    """Registra el modelo en el catalogo estatico del paquete langchain-nvidia.

    Por que existe: modelos recientes de NVIDIA Build API tardan en aparecer
    en el catalogo empaquetado de langchain-nvidia-ai-endpoints. Sin este
    registro, el paquete lanza warnings de 'type unknown' y 'not known to
    support tools', lo que puede bloquear el tool calling. Si en el futuro
    el modelo ya esta en el catalogo, esta funcion es un no-op inofensivo.
    """
    MODEL_TABLE[MODELO] = Model(
        id=MODELO,
        model_type="chat",
        client="ChatNVIDIA",
        supports_tools=True,
        supports_structured_output=True,
        supports_thinking=True,
        thinking_param_enable={"chat_template_kwargs": {"enable_thinking": True}},
        thinking_param_disable={"chat_template_kwargs": {"enable_thinking": False}},
    )


@tool
def tool_rag_pliegos(licitacion: str, pregunta: str) -> str:
    """Consulta las condiciones tecnicas, lotes y requisitos de un pliego PDF.

    Usala ante preguntas sobre el pliego en si: especificaciones tecnicas,
    licencias de un lote, requisitos de los proponentes, anexo tecnico.

    Args:
        licitacion: identificador del proceso, ej. IDARTES-SA-SI-013-2026
        pregunta: consulta en espanol sobre el pliego
    """
    rag = PliegoRAG(licitacion)
    if not rag.esta_indexada():
        rag.indexar(os.path.join("datos", "pliegos", licitacion))
    return formatear_resultados(rag.consultar_pliego(pregunta, k=3))


@tool
def tool_secop_proveedores(
    termino_clave: str,
    departamento: str = "Bogotá DC",
    codigo_unspsc: str | None = None,
) -> str:
    """Busca proveedores con experiencia en un tema en la contratacion estatal.

    Usala para saber que empresas han ganado contratos de un bien o servicio y
    cuanto suman (ej: software, licencias, soporte tecnico).

    Args:
        termino_clave: tema a buscar, ej. "software"
        departamento: departamento, ej. "Bogotá DC"
        codigo_unspsc: categoria UNSPSC opcional
    """
    return buscar_proveedores_secop(termino_clave, departamento, codigo_unspsc)


def crear_agente():
    """Construye el agente. Falla rapido si falta la clave de NVIDIA."""

    if not os.getenv("NVIDIA_API_KEY"):
        raise SystemExit(
            "Error: falta NVIDIA_API_KEY en el .env (copia .env-example a .env)."
        )

    _registrar_perfil_modelo()
    llm = ChatNVIDIA(
        model=MODELO,
        temperature=0,
        max_completion_tokens=2048,
        timeout=600,
        # El modelo razona por defecto; se apaga el thinking con el flag de su
        # model card. ChatNVIDIA lo transfiere a model_kwargs (equivalente al
        # ejemplo oficial chat_template_kwargs={...}).
        model_kwargs={"chat_template_kwargs": {"enable_thinking": False}},
    )
    return create_agent(
        model=llm,
        tools=[tool_rag_pliegos, tool_secop_proveedores],
        system_prompt=(
            "Eres un consultor experto en contratacion estatal colombiana. "
            "Para responder, primero consulta las condiciones tecnicas del "
            "pliego cargado con tool_rag_pliegos. Luego, con las palabras "
            "clave o codigos identificados, busca en tool_secop_proveedores "
            "los proveedores con mayor experiencia. Responde en espanol, "
            "citando la fuente y pagina del pliego cuando aplique."
        ),
        checkpointer=MemorySaver(),
    )


def responder(agente, pregunta: str, thread_id: str = "sesion-1") -> str:
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
    }
    resultado = agente.invoke({"messages": [("user", pregunta)]}, config=config)
    return resultado["messages"][-1].content


def main_cli() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Agente contratacion SECOP II")
    parser.add_argument(
        "pregunta", nargs="?", help="Pregunta en una linea (si se omite, modo interactivo)"
    )
    args = parser.parse_args()

    agente = crear_agente()

    # Modo una-pregunta: sin try/except — si algo falla, el traceback completo
    # es mas util que un mensaje generico (fail-fast)
    if args.pregunta:
        print(responder(agente, args.pregunta))
        return

    print("Agente SECOP II listo. Escribe una pregunta (q para salir):")
    while True:
        try:
            pregunta = input("> ").strip()
        except EOFError:
            print()
            break
        if pregunta.lower() == "q":
            print("Saliendo.")
            break
        if not pregunta:
            continue
        try:
            print(responder(agente, pregunta))
        except Exception as e:
            # MEJORA: se muestra el tipo del error ademas del mensaje para
            # facilitar el diagnostico sin ocultar el problema detras de un
            # mensaje generico
            print(f"[{type(e).__name__}] {e}")


if __name__ == "__main__":
    main_cli()