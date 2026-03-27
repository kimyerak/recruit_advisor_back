from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str
    mentor_id: str       # 선택된 멘토 ID
    job_id: str          # 선택된 채용공고 ID (없으면 빈 문자열)
    context: str         # RAG로 검색된 채용공고 내용
    intent: str          # "jd" | "resume" | "advice" — intent_node가 설정
    doc_relevance: str   # "relevant" | "not_relevant" | "" — grade_node가 설정
