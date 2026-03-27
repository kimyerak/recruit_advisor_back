"""
PDF를 파싱해서 벡터스토어에 저장하는 스크립트.

사용법:
    python -m backend.knowledge.ingest --pdf path/to/jd.pdf --job_id cloud-migration
"""
import argparse
from backend.knowledge.loader import load_pdf_with_vision
from backend.knowledge.vectorstore import ingest_documents


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, help="PDF 파일 경로")
    parser.add_argument("--job_id", required=True, help="채용공고 ID (예: cloud-migration)")
    args = parser.parse_args()

    print(f"[ingest] PDF 파싱 시작: {args.pdf}")
    docs = load_pdf_with_vision(args.pdf, args.job_id)
    print(f"[ingest] {len(docs)}페이지 파싱 완료, 벡터스토어 저장 중...")
    ingest_documents(docs)
    print("[ingest] 완료!")


if __name__ == "__main__":
    main()
