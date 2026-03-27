"""링커리어 페이지 구조 확인용 테스트 스크립트"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

LIST_URL = "https://linkareer.com/cover-letter/search?organizationName=kt&sort=RELEVANCE&tab=all&page=1"
DETAIL_URL = "https://linkareer.com/cover-letter/34105"


async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False로 실제 브라우저처럼
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        # 상세 페이지만 테스트
        print("=== 상세 페이지 테스트 ===")
        await page.goto(DETAIL_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        # 제목
        title = soup.find("h1") or soup.find("h2")
        print(f"제목: {title.get_text(strip=True)[:80] if title else '없음'}")

        # 파서 결과 확인
        from backend.knowledge.crawl_linkareer import parse_detail
        docs = parse_detail(html, 34105)
        print(f"→ 추출된 문서 {len(docs)}개\n")
        for i, doc in enumerate(docs, 1):
            print(f"── 문서 {i} ──")
            print(doc.page_content[:400])
            print()

        await browser.close()


asyncio.run(test())
