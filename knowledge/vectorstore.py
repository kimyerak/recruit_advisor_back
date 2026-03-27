from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from backend.config.settings import settings


def _get_store() -> Chroma:
    embeddings = OpenAIEmbeddings(model=settings.embedding_model)
    return Chroma(
        persist_directory=settings.vectorstore_path,
        embedding_function=embeddings,
        collection_name="jd_collection",
    )


def get_retriever(job_id: str | None = None):
    """job_id가 있으면 해당 채용공고만 필터링해서 검색"""
    store = _get_store()
    search_kwargs = {"k": 4}
    if job_id:
        search_kwargs["filter"] = {"job_id": job_id}
    return store.as_retriever(search_kwargs=search_kwargs)


def ingest_documents(documents: list[Document]) -> None:
    """파싱된 Document 리스트를 벡터스토어에 저장"""
    store = _get_store()
    store.add_documents(documents)
    print(f"[vectorstore] {len(documents)}개 문서 저장 완료")


def delete_job(job_id: str) -> None:
    """특정 채용공고 벡터 전체 삭제"""
    store = _get_store()
    store.delete(where={"job_id": job_id})
    print(f"[vectorstore] job_id={job_id} 삭제 완료")
