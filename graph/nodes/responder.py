from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, AIMessage
from backend.graph.state import ChatState
from backend.mentors.personas import CHARACTERS, BASE_PROMPT
from backend.config.settings import settings


_RESUME_GUIDANCE = """
[자소서 조언 모드]
지금은 KT 자기소개서 작성을 돕는 상황입니다.
- KT의 핵심가치(신뢰, 도전, 창의, 협력)와 지원 직무를 연결해서 조언하세요.
- 추상적인 말 대신 구체적인 소재·구조·표현을 제안하세요.
- 지원자가 자신의 경험을 꺼내도록 질문도 적극 활용하세요.
- 답변 분량, 문장 구조, 키워드 강조 방법도 함께 안내하세요."""


def _build_system_prompt(character_id: str, intent: str, context: str) -> str:
    character = CHARACTERS.get(character_id)
    if not character:
        return BASE_PROMPT

    parts = [
        BASE_PROMPT,
        f"\n\n[캐릭터 설정]\n{character.profile}",
    ]

    if context:
        label = {
            "jd": "채용공고 정보",
            "resume": "자소서 합격 사례",
            "advice": "선배 경험",
        }.get(intent, "참고 정보")
        parts.append(f"\n\n[{label}]\n{context}")

    if intent == "resume":
        parts.append(_RESUME_GUIDANCE)

    return "\n".join(parts)


def responder_node(state: ChatState) -> ChatState:
    """KT 브랜드 + 캐릭터 페르소나 + RAG 컨텍스트로 최종 답변 생성"""
    character = CHARACTERS.get(state["mentor_id"])
    if not character:
        return {"messages": [AIMessage(content="캐릭터를 찾을 수 없습니다. mentor_id를 확인해주세요. (vic 또는 ddory)")]}

    system_content = _build_system_prompt(
        character_id=state["mentor_id"],
        intent=state.get("intent", "advice"),
        context=state.get("context", ""),
    )

    llm = ChatOpenAI(model=settings.model_name, temperature=0.7)
    full_messages = [SystemMessage(content=system_content)] + state["messages"]
    response = llm.invoke(full_messages)

    return {"messages": [AIMessage(content=response.content)]}
