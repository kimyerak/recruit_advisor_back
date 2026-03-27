from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from backend.config.settings import settings


def _embeddings():
    return OpenAIEmbeddings(model=settings.emb_model_name)


def _get_jd_store() -> Chroma:
    return Chroma(
        persist_directory=settings.vectorstore_path,
        embedding_function=_embeddings(),
        collection_name="jd_collection",
    )


# ── JD 관련 ──────────────────────────────────────────

def get_retriever(job_id: str | None = None):
    """job_id가 있으면 해당 채용공고만 필터링해서 검색"""
    store = _get_jd_store()
    search_kwargs: dict = {"k": 4}
    if job_id:
        search_kwargs["filter"] = {"job_id": job_id}
    return store.as_retriever(search_kwargs=search_kwargs)


def ingest_documents(documents: list[Document]) -> None:
    """JD PDF 파싱 결과를 벡터스토어에 저장"""
    store = _get_jd_store()
    store.add_documents(documents)
    print(f"[vectorstore:jd] {len(documents)}개 문서 저장 완료")


def delete_job(job_id: str) -> None:
    store = _get_jd_store()
    store.delete(where={"job_id": job_id})
    print(f"[vectorstore:jd] job_id={job_id} 삭제 완료")


# ── 선배 경험 관련 ─────────────────────────────────────

def _get_senior_store() -> Chroma:
    return Chroma(
        persist_directory=settings.vectorstore_path,
        embedding_function=_embeddings(),
        collection_name="senior_collection",
    )


def get_senior_retriever():
    """KT 재직 선배 경험 검색 리트리버"""
    store = _get_senior_store()
    return store.as_retriever(search_kwargs={"k": 3})


def ingest_senior_documents(documents: list[Document]) -> None:
    """선배 경험 문서를 벡터스토어에 저장 (중복 방지: 기존 컬렉션 초기화 후 재저장)"""
    store = _get_senior_store()
    existing = store.get()
    if existing["ids"]:
        store.delete(ids=existing["ids"])
    store.add_documents(documents)
    print(f"[vectorstore:senior] {len(documents)}개 문서 저장 완료")
