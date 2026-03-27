from langchain_core.messages import HumanMessage
from backend.graph.state import ChatState
from backend.knowledge.vectorstore import get_retriever, get_linkareer_retriever


def rag_node(state: ChatState) -> ChatState:
    """intent에 따라 JD 또는 링커리어 자소서에서 컨텍스트 검색"""
    last_message = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )
    if not last_message:
        return {"context": ""}

    intent = state.get("intent", "jd")

    if intent == "resume":
        retriever = get_linkareer_retriever()
    else:
        retriever = get_retriever(job_id=state.get("job_id"))

    docs = retriever.invoke(last_message.content)
    context = "\n\n".join(d.page_content for d in docs)
    return {"context": context}
