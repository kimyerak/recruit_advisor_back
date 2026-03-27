from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from backend.graph.builder import graph

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    mentor_id: str
    job_id: str = ""
    message: str


class ChatResponse(BaseModel):
    reply: str
    session_id: str


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
            },
            config=config,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    last_message = result["messages"][-1]
    return ChatResponse(reply=last_message.content, session_id=req.session_id)
