import fitz  # PyMuPDF
import base64
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.documents import Document

def load_pdf_with_vision(pdf_path: str, job_id: str) -> list[Document]:
    """
    PDF 각 페이지를 이미지로 변환 후 Vision LLM으로 전체 내용 추출.
    텍스트 + 인포그래픽 모두 처리.
    """
    doc = fitz.open(pdf_path)
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    documents = []

    for page_num, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        img_b64 = base64.b64encode(pix.tobytes("png")).decode()

        response = llm.invoke([{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                },
                {
                    "type": "text",
                    "text": (
                        "이 채용공고 페이지의 모든 정보를 추출해줘. "
                        "직무명, 자격요건, 우대사항, 업무내용, 복지, 전형절차 등 "
                        "텍스트와 인포그래픽의 수치·내용을 빠짐없이 정리해줘."
                    )
                }
            ]
        }])

        documents.append(Document(
            page_content=response.content,
            metadata={
                "job_id": job_id,
                "source": Path(pdf_path).name,
                "page": page_num + 1,
            }
        ))

    return documents
