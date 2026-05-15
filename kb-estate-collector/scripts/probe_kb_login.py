"""KB 자동 로그인 검증 — 메뉴 → 로그인해보세요 → 휴대폰/이메일 → 폼 자동 입력."""
import asyncio
import json
import os

from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1440, "height": 900}, locale="ko-KR")
        page = await ctx.new_page()
        await page.goto("https://kbland.kr", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # 1. 좌측 GNB "메뉴" 클릭
        await page.evaluate(
            """() => [...document.querySelectorAll('.btn-gnb')]
                .find(b => b.innerText.trim() === '메뉴').click()"""
        )
        await asyncio.sleep(2)

        # 2. "로그인해보세요" 클릭
        await page.evaluate(
            """() => [...document.querySelectorAll('button')]
                .find(b => b.innerText.trim().startsWith('로그인해보세요')).click()"""
        )
        await asyncio.sleep(2)

        # 3. "휴대폰 또는 이메일 로그인" 클릭
        await page.evaluate(
            """() => {
                const b = [...document.querySelectorAll('button')]
                    .find(b => b.innerText.trim() === '휴대폰 또는 이메일 로그인'
                        && b.offsetParent !== null);
                if (b) b.click();
            }"""
        )
        await asyncio.sleep(3)
        await page.screenshot(path="/tmp/kb_7_form.png")

        # 4. 폼 자동 입력
        await page.fill(
            'input[placeholder="휴대폰 번호 또는 이메일 입력"]', os.environ["KB_LOGIN_ID"]
        )
        await page.fill('input[placeholder="비밀번호 입력"]', os.environ["KB_LOGIN_PASSWORD"])
        await page.screenshot(path="/tmp/kb_8_filled.png")

        # 5. 폼 부모 영역의 로그인 버튼 찾기
        btn_info = await page.evaluate(
            """() => {
                const pw = document.querySelector('input[placeholder="비밀번호 입력"]');
                if (!pw) return null;
                let el = pw;
                while (el && el !== document.body) {
                    if (el.tagName === 'FORM') return {parent: 'FORM', btns: [...el.querySelectorAll('button')].map(b => ({text: b.innerText.trim(), cls: (b.className||'').toString().slice(0,50), type: b.type}))};
                    el = el.parentElement;
                }
                // form 없으면 모든 visible button 중 "로그인" 텍스트
                return {parent: 'no form', btns: [...document.querySelectorAll('button')]
                    .filter(b => b.offsetParent !== null && b.innerText.trim() === '로그인')
                    .map(b => ({text: b.innerText.trim(), cls: (b.className||'').toString().slice(0,50), type: b.type}))};
            }"""
        )
        print("buttons in form:", json.dumps(btn_info, ensure_ascii=False))

        # 6. Enter 키로 제출
        await page.press('input[placeholder="비밀번호 입력"]', "Enter")
        await asyncio.sleep(5)
        await page.screenshot(path="/tmp/kb_9_after_submit.png")
        print(f"URL after submit: {page.url}")

        # 7. 쿠키 확인
        cookies = await ctx.cookies("https://kbland.kr")
        kb_cookies = [c for c in cookies if c["name"] in ("accessToken_", "refreshToken_")]
        print(f"KB session cookies: {len(kb_cookies)}")
        for c in kb_cookies:
            exp = c.get("expires", -1)
            print(f"  {c['name']}: {c['value'][:20]}... expires={exp}")

        # 8. 로그인 후 페이지 텍스트 첫 부분
        text = await page.evaluate("() => document.body.innerText.slice(0, 300)")
        print(f"page text:\n{text}")

        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
