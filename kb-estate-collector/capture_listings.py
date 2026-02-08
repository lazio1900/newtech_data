"""Capture listing API calls from KB website property list page."""
import asyncio
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')


async def capture():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        api_calls = []

        async def on_response(response):
            url = response.url
            if 'api.kbland.kr' in url:
                try:
                    body = await response.json()
                    entry = {
                        'url': url,
                        'method': response.request.method,
                        'status': response.status,
                        'headers': dict(response.request.headers),
                    }
                    # Capture POST body
                    if response.request.method == 'POST':
                        entry['post_data'] = response.request.post_data
                    # Capture response summary
                    if isinstance(body, dict):
                        db = body.get('dataBody', {})
                        entry['resultCode'] = db.get('resultCode')
                        data = db.get('data')
                        if isinstance(data, dict):
                            entry['data_keys'] = list(data.keys())
                            for k, v in data.items():
                                if isinstance(v, list):
                                    entry[f'data.{k}_count'] = len(v)
                                    if v:
                                        entry[f'data.{k}_first'] = json.dumps(v[0], ensure_ascii=False)[:500]
                        elif isinstance(data, list):
                            entry['data_count'] = len(data)
                            if data:
                                entry['data_first'] = json.dumps(data[0], ensure_ascii=False)[:500]
                    api_calls.append(entry)
                except Exception:
                    pass

        page.on('response', on_response)

        # Navigate to property list page for 동아 complex (971)
        print("Navigating to property list page...")
        url = 'https://kbland.kr/pl/971?xy=37.6564503,127.0811642,15'
        await page.goto(url, wait_until='networkidle', timeout=60000)
        await asyncio.sleep(5)

        print(f"\nCaptured {len(api_calls)} API calls:")
        for i, call in enumerate(api_calls):
            url_short = call['url'].split('?')[0].replace('https://api.kbland.kr', '')
            method = call['method']
            rc = call.get('resultCode', '?')
            print(f"\n[{i+1}] [{method}] {url_short}  rc={rc}")
            if call.get('data_keys'):
                print(f"    keys: {call['data_keys']}")
            for k, v in call.items():
                if k.endswith('_count'):
                    print(f"    {k}: {v}")
                if k.endswith('_first'):
                    print(f"    {k}: {v[:300]}")
            if call.get('post_data'):
                print(f"    POST: {call['post_data'][:400]}")
            if method == 'GET' and '?' in call['url']:
                from urllib.parse import unquote
                params = unquote(call['url'].split('?', 1)[1])
                print(f"    GET params: {params[:400]}")

        # Save full capture
        with open('captured_listing_calls.json', 'w', encoding='utf-8') as f:
            json.dump(api_calls, f, ensure_ascii=False, indent=2, default=str)
        print(f"\nSaved to captured_listing_calls.json")

        await browser.close()


asyncio.run(capture())
