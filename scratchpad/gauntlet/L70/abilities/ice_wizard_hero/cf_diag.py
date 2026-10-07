import time
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(channel="chrome", headless=False, args=["--disable-blink-features=AutomationControlled"])
    p = b.new_context().new_page()
    p.goto("https://royaleapi.com/", wait_until="domcontentloaded", timeout=60000)
    for i in range(6):
        time.sleep(5)
        print(i, p.title()[:60], p.url)
    p.screenshot(path="cf_diag.png")
    print([c["name"] for c in p.context.cookies()])
    b.close()
