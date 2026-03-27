from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from backend.graph.state import ChatState
from backend.graph.nodes.intent import intent_node
from backend.graph.nodes.rag import rag_node
from backend.graph.nodes.responder import responder_node


def _route(state: ChatState) -> str:
    """intent에 따라 RAG 필요 여부 결정"""
    intent = state.get("intent", "advice")
    if intent in ("jd", "resume"):
        return "rag"
    return "responder"  # advice는 RAG 없이 바로 응답


def build_graph():
    g = StateGraph(ChatState)

    g.add_node("intent", intent_node)
    g.add_node("rag", rag_node)
    g.add_node("responder", responder_node)

    g.add_edge(START, "intent")
    g.add_conditional_edges("intent", _route, {"rag": "rag", "responder": "responder"})
    g.add_edge("rag", "responder")
    g.add_edge("responder", END)

    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)


graph = build_graph()
