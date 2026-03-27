from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from backend.graph.state import ChatState
from backend.config.settings import settings

INTENT_SYSTEM = """사용자 메시지를 읽고 의도를 아래 3가지 중 하나로만 답해.
다른 말은 절대 하지 말고 단어 하나만 출력.

- jd       : 채용공고 내용, 자격요건, 업무, 근무조건 관련 질문
- resume   : 자기소개서 작성, 면접 준비, 지원 전략 관련 질문
- advice   : 커리어 고민, 직무 선택, 취업 준비 전반 조언

예시:
"자격요건이 어떻게 되나요?" → jd
"자소서 1번 항목 어떻게 쓰면 될까요?" → resume
"KT 어떤 직무가 저한테 맞을까요?" → advice
"""


def intent_node(state: ChatState) -> ChatState:
    last_message = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )
    if not last_message:
        return {"intent": "advice"}

    llm = ChatOpenAI(model=settings.model_name, temperature=0)
    result = llm.invoke([
        SystemMessage(content=INTENT_SYSTEM),
        HumanMessage(content=last_message.content),
    ])

    intent = result.content.strip().lower()
    if intent not in ("jd", "resume", "advice"):
        intent = "advice"

    return {"intent": intent}
