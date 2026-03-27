from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from backend.graph.state import ChatState
from backend.graph.nodes.intent import intent_node
from backend.graph.nodes.rag import rag_node
from backend.graph.nodes.grade import grade_node
from backend.graph.nodes.responder import responder_node


def _route_after_intent(state: ChatState) -> str:
    """LLM이 분류한 intent로 라우팅 — 모든 intent가 RAG를 거침
    jd→채용공고DB, resume→자소서DB, advice→선배경험DB"""
    return "rag"


def _route_after_grade(state: ChatState) -> str:
    """문서 관련성 평가 결과로 라우팅"""
    if state.get("doc_relevance") == "relevant":
        return "responder"
    return "clear_context"


def clear_context_node(state: ChatState) -> dict:
    """관련 없는 문서는 버리고 LLM 자체 지식으로 응답"""
    return {"context": ""}


def build_graph():
    g = StateGraph(ChatState)

    g.add_node("intent",        intent_node)
    g.add_node("rag",           rag_node)
    g.add_node("grade",         grade_node)
    g.add_node("clear_context", clear_context_node)
    g.add_node("responder",     responder_node)

    g.add_edge(START, "intent")

    g.add_conditional_edges(
        "intent",
        _route_after_intent,
        {"rag": "rag"},
    )

    g.add_edge("rag", "grade")

    g.add_conditional_edges(
        "grade",
        _route_after_grade,
        {"responder": "responder", "clear_context": "clear_context"},
    )

    g.add_edge("clear_context", "responder")
    g.add_edge("responder", END)

    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)


graph = build_graph()
