"""
PDF 생성 테스트 스크립트
Windows PC에서 실행: python test/test_pdf.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_simple_pdf():
    """간단한 텍스트로 PDF 생성 테스트"""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="msedge")
        except Exception:
            browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content("""
        <html><body style="font-family: sans-serif; padding: 40px;">
            <h1>FA 분석 PDF 테스트</h1>
            <p>PDF 생성이 정상적으로 동작합니다.</p>
            <p>이 파일이 생성되면 Knox Messenger 전송 준비 완료!</p>
        </body></html>
        """)
        out = os.path.join(os.path.dirname(__file__), "test_output.pdf")
        await page.pdf(path=out, format="A4", print_background=True)
        await browser.close()
        print(f"✅ PDF 생성 완료: {out}")


async def test_html_to_pdf():
    """sample_analysis.html → PDF 변환 테스트"""
    from app.analysis.pdf_generator import html_to_pdf

    html_path = os.path.join(os.path.dirname(__file__), "sample_analysis.html")
    pdf_path = os.path.join(os.path.dirname(__file__), "sample_analysis.pdf")

    if not os.path.exists(html_path):
        print("❌ sample_analysis.html 없음 - 먼저 SN 조회로 생성하세요")
        return

    success = await html_to_pdf(html_path, pdf_path)
    if success:
        print(f"✅ HTML→PDF 변환 완료: {pdf_path}")
    else:
        print("❌ 변환 실패 - 로그 확인")


if __name__ == "__main__":
    print("=== 테스트 1: 간단한 텍스트 PDF ===")
    asyncio.run(test_simple_pdf())
    print()
    print("=== 테스트 2: 분석 HTML → PDF ===")
    asyncio.run(test_html_to_pdf())
