import json
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from backend.graph.builder import graph
from backend.config.settings import settings

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    mentor_id: str
    job_id: str = ""
    message: str


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    suggestions: list[str] = []


async def _generate_suggestions(reply: str, intent: str) -> list[str]:
    """답변 기반으로 후속 질문 3개 생성"""
    intent_hint = {
        "jd": "채용공고, 자격요건, 근무환경, 직무 내용",
        "advice": "실무 경험, 팀 분위기, 커리어 성장, 회사 문화",
        "resume": "자소서 항목, 표현 방식, KT 핵심가치, 면접 준비",
    }.get(intent, "취업 준비")

    llm = ChatOpenAI(model=settings.model_name, temperature=0.8)
    prompt = f"""아래 멘토 답변을 읽고, 취준생이 이어서 물어볼 만한 짧은 질문 3개를 만들어줘.
주제 힌트: {intent_hint}
멘토 답변: {reply[:600]}

규칙:
- 각 질문은 15자 이내로 짧고 구체적으로
- JSON 배열로만 답해 (다른 말 없이): ["질문1", "질문2", "질문3"]"""

    try:
        result = llm.invoke([HumanMessage(content=prompt)])
        return json.loads(result.content.strip())
    except Exception:
        return []


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    config = {"configurable": {"thread_id": req.session_id}}

    try:
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=req.message)],
                "session_id": req.session_id,
                "mentor_id": req.mentor_id,
                "job_id": req.job_id,
                "context": "",
                "intent": "",
                "doc_relevance": "",
            },
            config=config,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    reply = result["messages"][-1].content

    # 메인 답변과 후속 질문 생성 병렬 실행
    suggestions = await _generate_suggestions(reply, result.get("intent", "advice"))

    return ChatResponse(reply=reply, session_id=req.session_id, suggestions=suggestions)
