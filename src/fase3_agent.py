"""Fase 3: Agente orquestador (LangChain + NVIDIA Build API).

Une el RAG de pliegos (Fase 1) y la busqueda de proveedores (Fase 2) en un
agente que responde preguntas sobre licitaciones, decidiendo que tool usar.
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.tools import tool
from langchain_nvidia_ai_endpoints import ChatNVIDIA, Model
from langchain_nvidia_ai_endpoints._statics import MODEL_TABLE
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError

from src.fase1_rag_engine import PliegoRAG, formatear_resultados
from src.fase2_secop_tools import buscar_proveedores_secop

load_dotenv()  # carga NVIDIA_API_KEY desde el .env (sin leerlo)

MODELO = "nvidia/nemotron-3.5-lightning-30b-a3b"
# Cada ToolCallLimitMiddleware suma sus propios pasos de before/after_model;
# 12 no alcanzaba para rag -> secop -> respuesta final y se perdia una
# respuesta ya generada por corte de recursion_limit.
RECURSION_LIMIT = 20


def _registrar_perfil_modelo() -> None:
    """Registra el modelo en el catalogo estatico del paquete langchain-nvidia.

    Evita los warnings de "type unknown" y "not known to support tools" y deja
    que el paquete sepa que soporta tool calling.
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

    Usala ante preguntas sobre el pliego en si: que busque un objeto contractual parecido con un texto corto.

    Args:
        licitacion: identificador del proceso, ej. IDARTES-SA-SI-013-2026
        pregunta: consulta amplia en espanol sobre el pliego
    """
    rag = PliegoRAG(licitacion)
    if not rag.esta_indexada():
        rag.indexar(os.path.join("datos", "pliegos", licitacion))
    rag = formatear_resultados(rag.consultar_pliego(pregunta, k=8))
    print(f"RAG: {rag[:200]}...")  # debug
    return rag


@tool
def tool_secop_proveedores(
    termino_clave: str,
    departamento: str = "Bogotá DC",
    codigo_unspsc: str | None = None,
) -> str:
    """Busca proveedores con experiencia en un tema en la contratacion estatal.

    Usala para saber que empresas han ganado contratos de un bien o servicio y
    cuanto suman (ej: software, licencias, soporte tecnico). El buscador hace
    match literal, asi que usa una sola palabra clave (no frases largas); si
    no hay resultados, prueba con otra palabra unica, no repitas variantes
    de la misma frase.

    Args:
        termino_clave: una sola palabra clave, ej. "software"
        departamento: departamento, ej. "Bogotá DC"
        codigo_unspsc: categoria UNSPSC opcional
    """
    proveedor= buscar_proveedores_secop(termino_clave, departamento, codigo_unspsc)
    print(f"Proveedores: {proveedor[:200]}...")  # debug
    return proveedor


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
        # El modelo es pequeño y tiende a repetir tool_rag_pliegos con
        # preguntas casi identicas; "continue" en el limite por-tool le deja
        # ver el error y cambiar de estrategia (ir a tool_secop_proveedores)
        # en vez de terminar el turno entero como hace "end".
        middleware=[
            ToolCallLimitMiddleware(tool_name="tool_rag_pliegos", run_limit=1, exit_behavior="continue"),
            # 2, no 1: una llamada con argumentos invalidos (el modelo a
            # veces manda {} y falla la validacion antes de ejecutar la
            # tool) ya consume el cupo y bloquea el reintento correcto.
            ToolCallLimitMiddleware(tool_name="tool_secop_proveedores", run_limit=2, exit_behavior="continue"),
            ToolCallLimitMiddleware(run_limit=5, exit_behavior="end"),
        ],
        system_prompt=(
            "Eres un consultor experto en contratacion estatal colombiana. "
            "Primero llama UNA vez a tool_rag_pliegos con una sola pregunta "
            "amplia que cubra lotes, licencias y requisitos a la vez (no la "
            "dividas en varias llamadas). Luego llama hasta dos veces a "
            "tool_secop_proveedores con una palabra clave identificada en el "
            "pliego. Ejemplo software de diseño. Esta tool responde con una tabla en markdown y esta bien, pues pueden existir muchos proveedores. Responde en espanol citando la "
            "fuente . pagina del pliego cuando aplique. Nunca termines tu "
            "turno con una respuesta vacia: redacta la respuesta con lo que "
            "ya obtuviste de las herramientas antes de terminar."
        ),
        checkpointer=MemorySaver(),
        debug=True,
    )


def responder(agente, pregunta: str, thread_id: str = "sesion-1") -> str:
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
    }
    try:
        resultado = agente.invoke({"messages": [("user", pregunta)]}, config=config)
        return resultado["messages"][-1].content
    except GraphRecursionError:
        # El modelo puede haber generado ya una respuesta final justo en el
        # paso que agoto el limite; el checkpointer la conserva aunque
        # invoke() lance la excepcion, asi que se recupera de ahi.
        ultimo_estado = agente.get_state(config).values.get("messages", [])
        if ultimo_estado and ultimo_estado[-1].content.strip():
            return ultimo_estado[-1].content
        return (
            "No pude cerrar una respuesta dentro del limite de pasos "
            "permitidos (el modelo siguio intentando llamar herramientas). "
            "Intenta reformular la pregunta o dividela en partes mas simples."
        )


def main_cli() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Agente contratacion SECOP II")
    parser.add_argument(
        "pregunta", nargs="?", help="Pregunta en una linea (si se omite, modo interactivo)"
    )
    args = parser.parse_args()

    agente = crear_agente()

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
            print(f"Error procesando la pregunta: {e}")


if __name__ == "__main__":
    main_cli()