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

    if intent == "resume":
        system_content += """

[자소서 조언 모드]
지금은 KT 자기소개서 작성을 돕는 상황입니다.
- KT의 핵심가치(신뢰, 도전, 창의, 협력)와 지원 직무를 연결해서 조언하세요.
- 추상적인 말 대신 구체적인 소재·구조·표현을 제안하세요.
- 지원자가 자신의 경험을 꺼내도록 질문도 적극 활용하세요.
- 답변 분량, 문장 구조, 키워드 강조 방법도 함께 안내하세요."""
    elif intent == "jd" and context:
        system_content += f"\n\n[채용공고 정보]\n{context}"

    llm = ChatOpenAI(model=settings.model_name, temperature=0.7)

    # SystemMessage + 전체 대화 히스토리로 멀티턴 유지
    full_messages = [SystemMessage(content=system_content)] + state["messages"]
    response = llm.invoke(full_messages)

    return {"messages": [AIMessage(content=response.content)]}
