import asyncio, json

async def test():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await page.add_init_script("""
        window.__capturedBodies = [];
        const origSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function(body) {
            if (this.__url && this.__url.includes('stutCdFilter')) {
                window.__capturedBodies.push(body);
            }
            return origSend.call(this, body);
        };
        const origOpen = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(method, url) {
            this.__url = url;
            return origOpen.apply(this, arguments);
        };
        """)

        await page.goto('https://kbland.kr/map?xy=37.4938690,127.0509446,18&complex=Y&complexNo=13886',
                       wait_until='networkidle', timeout=60000)
        await asyncio.sleep(5)

        # Get full body as JSON string from browser, write to file
        raw_body = await page.evaluate("""
        () => {
            if (window.__capturedBodies.length === 0) return null;
            return window.__capturedBodies[0];
        }
        """)

        if raw_body:
            # Write raw JSON body to file
            with open('captured_stutcd_body.json', 'w', encoding='utf-8') as f:
                f.write(raw_body)

            # Parse and re-dump with ensure_ascii to see actual unicode
            parsed = json.loads(raw_body)
            with open('captured_stutcd_parsed.json', 'w', encoding='utf-8') as f:
                json.dump(parsed, f, ensure_ascii=True, indent=2)

            print(f"Captured {len(parsed)} params")
            print("Saved to captured_stutcd_body.json and captured_stutcd_parsed.json")
        else:
            print("No captures")

        await browser.close()

asyncio.run(test())
