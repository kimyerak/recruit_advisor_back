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
    intent = state.get("intent", "advice")

    system_content = mentor.system_prompt
    if context:
        if intent == "resume":
            system_content += f"\n\n[KT 합격 선배들의 실제 자소서 예시]\n아래 자소서를 참고해서 구체적인 조언을 해줘.\n{context}"
        else:
            system_content += f"\n\n[채용공고 정보]\n{context}"

    llm = ChatOpenAI(model=settings.model_name, temperature=0.7)

    # SystemMessage + 전체 대화 히스토리로 멀티턴 유지
    full_messages = [SystemMessage(content=system_content)] + state["messages"]
    response = llm.invoke(full_messages)

    return {"messages": [AIMessage(content=response.content)]}
