"""
링커리어 KT 자소서 크롤링 후 벡터스토어 저장 스크립트.

사용법:
    playwright install chromium  # 최초 1회
    python -m backend.knowledge.crawl_linkareer --pages 3
"""
import asyncio
import argparse
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from langchain_core.documents import Document
from backend.knowledge.vectorstore import ingest_linkareer_documents

BASE_URL = "https://linkareer.com"
LIST_URL = "https://linkareer.com/cover-letter/search?organizationName=kt&sort=RELEVANCE&tab=all&page={page}"
DETAIL_URL = "https://linkareer.com/cover-letter/{cid}"


async def fetch_html(page, url: str) -> str:
    await page.goto(url, wait_until="networkidle", timeout=30000)
    return await page.content()


def parse_cover_letter_ids(html: str) -> list[int]:
    """목록 페이지에서 자소서 ID 추출"""
    soup = BeautifulSoup(html, "html.parser")
    ids = []
    for a in soup.find_all("a", href=True):
        m = re.match(r"/cover-letter/(\d+)", a["href"])
        if m:
            ids.append(int(m.group(1)))
    return list(set(ids))


def parse_detail(html: str, cid: int) -> list[Document]:
    """상세 페이지에서 KT 자소서 질문+답변만 파싱"""
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text(separator="\n", strip=True)

    # ── 타이틀 추출 ──────────────────────────────────────
    # "합격 자소서" 섹션 이후 첫 번째 "KT / ..." 줄
    title = "KT 자소서"
    m = re.search(r"합격 자소서\n(KT\s*/[^\n]+)", full_text)
    if m:
        title = m.group(1).strip()

    # ── 본문 범위 추출 ────────────────────────────────────
    # "이 글은 KT" → 실제 자소서 소개 시작점
    # "새창" / "자바스크립트" → 푸터 시작점
    body = full_text
    start = full_text.find("이 글은 KT")
    if start == -1:
        start = full_text.find("합격 자소서")
    end_markers = ["새창\n새창", "새창\n목록", "자바스크립트가 작동하지 않는"]
    end = len(full_text)
    for marker in end_markers:
        idx = full_text.find(marker, start)
        if idx != -1:
            end = min(end, idx)
    if start != -1:
        body = full_text[start:end]

    # ── 번호 기준 질문+답변 분리 ─────────────────────────
    # 패턴: "1. 질문 내용\n답변..."  "2. 질문 내용\n답변..."
    qa_pattern = re.compile(r"(\d+\.\s{0,2}.{10,}?\n)([\s\S]+?)(?=\n\d+\.\s|\Z)")
    blocks = qa_pattern.findall(body)

    docs = []
    if blocks:
        for question_raw, answer_raw in blocks:
            question = question_raw.strip()
            answer = re.sub(r"\n+", " ", answer_raw).strip()
            if len(answer) < 30:  # 너무 짧은 답변 제외
                continue
            docs.append(Document(
                page_content=f"[KT 합격 자소서]\n직무: {title}\n\n질문: {question}\n답변: {answer}",
                metadata={"source": "linkareer", "cover_letter_id": cid, "title": title, "question": question},
            ))

    if not docs:
        # fallback: 본문 전체를 하나의 문서로
        clean = re.sub(r"\n{3,}", "\n\n", body).strip()
        docs.append(Document(
            page_content=f"[KT 합격 자소서]\n직무: {title}\n\n{clean[:3000]}",
            metadata={"source": "linkareer", "cover_letter_id": cid, "title": title},
        ))

    return docs


async def crawl(num_pages: int = 3) -> list[Document]:
    all_docs: list[Document] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # 1. 목록 페이지에서 자소서 ID 수집
        all_ids: list[int] = []
        for pg in range(1, num_pages + 1):
            print(f"[crawl] 목록 페이지 {pg}/{num_pages} 수집 중...")
            html = await fetch_html(page, LIST_URL.format(page=pg))
            ids = parse_cover_letter_ids(html)
            all_ids.extend(ids)
            print(f"  → {len(ids)}개 ID 발견")

        all_ids = list(set(all_ids))
        print(f"[crawl] 총 {len(all_ids)}개 자소서 수집 예정")

        # 2. 상세 페이지 크롤링
        for i, cid in enumerate(all_ids, 1):
            print(f"[crawl] 자소서 상세 {i}/{len(all_ids)} (id={cid})")
            try:
                html = await fetch_html(page, DETAIL_URL.format(cid=cid))
                docs = parse_detail(html, cid)
                all_docs.extend(docs)
                print(f"  → {len(docs)}개 문서 파싱")
            except Exception as e:
                print(f"  → 실패: {e}")

        await browser.close()

    return all_docs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=3, help="크롤링할 목록 페이지 수")
    args = parser.parse_args()

    docs = asyncio.run(crawl(args.pages))
    print(f"\n[crawl] 총 {len(docs)}개 문서 벡터스토어 저장 중...")
    ingest_linkareer_documents(docs)
    print("[crawl] 완료!")


if __name__ == "__main__":
    main()
