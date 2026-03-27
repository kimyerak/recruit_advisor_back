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
    """상세 페이지에서 자소서 질문+답변 파싱"""
    soup = BeautifulSoup(html, "html.parser")
    docs = []

    # 회사명/공고 타이틀
    title_tag = soup.find("h1") or soup.find("h2")
    title = title_tag.get_text(strip=True) if title_tag else "KT 자소서"

    # 질문+답변 블록 추출 (링커리어 공통 구조)
    # 질문은 보통 strong/h3/b 태그, 답변은 p 태그
    blocks = []
    for tag in soup.find_all(["h3", "strong", "b"]):
        text = tag.get_text(strip=True)
        if len(text) > 10:  # 짧은 UI 텍스트 제외
            answer_parts = []
            for sib in tag.find_next_siblings():
                if sib.name in ["h3", "strong", "b"]:
                    break
                t = sib.get_text(strip=True)
                if t:
                    answer_parts.append(t)
            if answer_parts:
                blocks.append((text, " ".join(answer_parts)))

    if not blocks:
        # fallback: 전체 본문을 하나의 문서로
        body = soup.get_text(separator="\n", strip=True)
        docs.append(Document(
            page_content=f"[KT 합격 자소서]\n{body[:3000]}",
            metadata={"source": "linkareer", "cover_letter_id": cid, "title": title},
        ))
    else:
        for q, a in blocks:
            docs.append(Document(
                page_content=f"[KT 자소서 항목]\n질문: {q}\n답변: {a}",
                metadata={"source": "linkareer", "cover_letter_id": cid, "title": title, "question": q},
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
