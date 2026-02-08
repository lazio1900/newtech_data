"""Capture transaction API calls from KB website by navigating to a complex and clicking 실거래가 tab."""
import asyncio
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')


async def test():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        all_api_calls = []

        async def on_response(response):
            url = response.url
            if 'api.kbland.kr' in url:
                try:
                    body = await response.json()
                    all_api_calls.append({
                        'url': url,
                        'method': response.request.method,
                        'post_data': response.request.post_data,
                        'response': body,
                    })
                except:
                    pass

        page.on('response', on_response)

        # Navigate to a complex - 도곡렉슬 (13886)
        print("Navigating to 도곡렉슬 complex page...")
        await page.goto(
            'https://kbland.kr/map?xy=37.4938690,127.0509446,18&complex=Y&complexNo=13886',
            wait_until='networkidle',
            timeout=60000,
        )
        await asyncio.sleep(5)

        print(f"\nInitial load: {len(all_api_calls)} API calls")

        # Try to open the complex detail panel by clicking on the complex marker
        # The marker might be a canvas element, so let's try clicking at center
        viewport = page.viewport_size
        if viewport:
            cx, cy = viewport['width'] // 2, viewport['height'] // 2
            print(f"Clicking at center ({cx}, {cy})")
            await page.mouse.click(cx, cy)
            await asyncio.sleep(3)

        initial_count = len(all_api_calls)

        # Find and click the complex name or detail panel
        # Look for any clickable element that opens the complex detail
        for selector in ['[class*=complex]', '[class*=detail]', '[class*=info]']:
            elements = await page.query_selector_all(selector)
            for el in elements[:3]:
                text = await el.text_content()
                if text and len(text.strip()) < 50:
                    visible = await el.is_visible()
                    if visible:
                        print(f"Found element: {text.strip()[:30]}")

        # Now look for the actual tab buttons in the complex panel
        print("\nSearching for tab elements...")
        all_buttons = await page.query_selector_all('button, [role=tab], a, span')
        tab_candidates = []
        for btn in all_buttons:
            text = await btn.text_content()
            if text:
                text = text.strip()
                visible = await btn.is_visible()
                if visible and 0 < len(text) < 20:
                    tab_candidates.append((btn, text))

        print(f"Visible buttons/tabs: {[t for _, t in tab_candidates[:30]]}")

        # Click 실거래가 related tab
        all_api_calls_before_click = len(all_api_calls)
        clicked = False
        for btn, text in tab_candidates:
            if '실거래' in text or '거래' in text:
                print(f"\nClicking tab: {text}")
                await btn.click()
                await asyncio.sleep(5)
                clicked = True
                break

        if not clicked:
            # Try clicking text directly
            for search in ['실거래가', '실거래', '거래가격']:
                try:
                    loc = page.locator(f'text="{search}"').first
                    if await loc.is_visible(timeout=2000):
                        await loc.click()
                        await asyncio.sleep(5)
                        print(f"Clicked: {search}")
                        clicked = True
                        break
                except:
                    pass

        new_calls = all_api_calls[all_api_calls_before_click:]
        print(f"\nNew API calls after tab click: {len(new_calls)}")
        for call in new_calls:
            url_short = call['url'].split('?')[0].replace('https://api.kbland.kr', '')
            rc = call['response'].get('dataBody', {}).get('resultCode', '?')
            data = call['response'].get('dataBody', {}).get('data')
            has_data = data is not None
            print(f"  [{call['method']}] {url_short} rc={rc} data={has_data}")
            if has_data and isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, list):
                        print(f"    {k}: {len(v)} items")
                        if v:
                            print(f"    first: {json.dumps(v[0], ensure_ascii=False)[:300]}")
                    else:
                        print(f"    {k}: {str(v)[:100]}")
            elif has_data and isinstance(data, list):
                print(f"    list: {len(data)} items")
                if data:
                    print(f"    first: {json.dumps(data[0], ensure_ascii=False)[:300]}")
            if call.get('post_data'):
                print(f"    post: {call['post_data'][:200]}")
            if call['method'] == 'GET' and '?' in call['url']:
                from urllib.parse import unquote
                print(f"    params: {unquote(call['url'].split('?', 1)[1])[:200]}")

        # Dump all API calls summary
        print(f"\n=== ALL {len(all_api_calls)} API CALLS ===")
        for call in all_api_calls:
            url_short = call['url'].split('?')[0].replace('https://api.kbland.kr', '')
            rc = call['response'].get('dataBody', {}).get('resultCode', '?')
            data = call['response'].get('dataBody', {}).get('data')
            has_data = data is not None
            print(f"  [{call['method']}] {url_short} rc={rc} data={has_data}")

        await browser.close()


asyncio.run(test())
