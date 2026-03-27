from langchain_core.messages import HumanMessage
from backend.graph.state import ChatState
from backend.knowledge.vectorstore import get_retriever

def rag_node(state: ChatState) -> ChatState:
    """사용자 질문과 선택된 채용공고 기반으로 관련 문서 검색"""
    last_message = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )
    if not last_message:
        return {"context": ""}

    retriever = get_retriever(job_id=state.get("job_id"))
    docs = retriever.invoke(last_message.content)
    context = "\n\n".join(d.page_content for d in docs)
    return {"context": context}
