from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from backend.graph.state import ChatState
from backend.graph.nodes.rag import rag_node
from backend.graph.nodes.responder import responder_node

def build_graph():
    g = StateGraph(ChatState)

    g.add_node("rag", rag_node)
    g.add_node("responder", responder_node)

    g.add_edge(START, "rag")
    g.add_edge("rag", "responder")
    g.add_edge("responder", END)

    checkpointer = MemorySaver()
    return g.compile(checkpointer=checkpointer)

graph = build_graph()
