from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from backend.graph.state import ChatState
from backend.config.settings import settings

GRADE_SYSTEM = """사용자 질문과 검색된 문서를 읽고, 문서가 질문에 답하는 데 유용한지 판단해.
"relevant" 또는 "not_relevant" 중 하나만 출력해. 다른 말은 하지 마.

- relevant     : 문서에 질문에 직접 답할 수 있는 정보가 포함됨
- not_relevant : 문서가 질문과 관련 없거나 답변에 도움이 안 됨"""


def grade_node(state: ChatState) -> dict:
    """검색된 문서가 질문과 관련 있는지 LLM으로 평가"""
    if not state.get("context"):
        return {"doc_relevance": "not_relevant"}

    last_message = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )
    if not last_message:
        return {"doc_relevance": "not_relevant"}

    grading_input = f"[질문]\n{last_message.content}\n\n[검색된 문서]\n{state['context'][:2000]}"

    try:
        llm = ChatOpenAI(model=settings.model_name, temperature=0)
        result = llm.invoke([
            SystemMessage(content=GRADE_SYSTEM),
            HumanMessage(content=grading_input),
        ])
        grade = result.content.strip().lower()
        return {"doc_relevance": "relevant" if grade == "relevant" else "not_relevant"}
    except Exception:
        return {"doc_relevance": "not_relevant"}
