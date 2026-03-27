from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from backend.graph.state import ChatState
from backend.mentors.personas import MENTORS
from backend.config.settings import settings

def responder_node(state: ChatState) -> ChatState:
    """멘토 페르소나 + RAG 컨텍스트로 최종 답변 생성"""
    mentor = MENTORS.get(state["mentor_id"])
    if not mentor:
        return {"messages": [AIMessage(content="멘토를 찾을 수 없습니다.")]}

    context = state.get("context", "")

    system_content = mentor.system_prompt
    if context:
        system_content += f"\n\n[채용공고 정보]\n{context}"

    llm = ChatOpenAI(model=settings.model_name, temperature=0.7)

    # SystemMessage + 전체 대화 히스토리로 멀티턴 유지
    full_messages = [SystemMessage(content=system_content)] + state["messages"]
    response = llm.invoke(full_messages)

    return {"messages": [AIMessage(content=response.content)]}
