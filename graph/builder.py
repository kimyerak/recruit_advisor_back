from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from backend.graph.state import ChatState
from backend.graph.nodes.rag import rag_node
from backend.graph.nodes.responder import responder_node


def _route(state: ChatState) -> str:
    """프론트에서 전달된 intent로 바로 라우팅 (LLM 추측 없음)"""
    intent = state.get("intent", "story")
    if intent in ("jd", "resume"):
        return "rag"
    return "responder"  # story는 RAG 없이 페르소나만


def build_graph():
    g = StateGraph(ChatState)

    g.add_node("rag", rag_node)
    g.add_node("responder", responder_node)

    g.add_conditional_edges(START, _route, {"rag": "rag", "responder": "responder"})
    g.add_edge("rag", "responder")
    g.add_edge("responder", END)

    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)


graph = build_graph()
