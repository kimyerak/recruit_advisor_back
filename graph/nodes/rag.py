from langchain_core.messages import HumanMessage
from backend.graph.state import ChatState
from backend.knowledge.vectorstore import get_retriever, get_senior_retriever


def rag_node(state: ChatState) -> ChatState:
    """intent에 따라 적절한 벡터스토어에서 컨텍스트 검색"""
    last_message = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )
    if not last_message:
        return {"context": ""}

    intent = state.get("intent", "jd")
    try:
        if intent == "jd":
            retriever = get_retriever(job_id=state.get("job_id"))
        else:  # resume, advice 모두 선배 경험 DB
            retriever = get_senior_retriever()
        docs = retriever.invoke(last_message.content)
        context = "\n\n".join(d.page_content for d in docs)
    except Exception:
        context = ""

    return {"context": context}
