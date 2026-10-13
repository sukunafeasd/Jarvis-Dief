"""Check the public WhatsApp Web login without linking an account or sending."""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as pw:
        edge=Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
        browser=await pw.chromium.launch(headless=True,**({"executable_path":str(edge)} if edge.exists() else {}))
        try:
            context=await browser.new_context(locale="pt-BR")
            page=await context.new_page()
            await page.goto("https://web.whatsapp.com",wait_until="domcontentloaded",timeout=35000)
            await page.wait_for_timeout(8000)
            text=(await page.locator("body").inner_text()).lower()
            result={"title":await page.title(),"connected":bool(await page.locator("#pane-side").count()),
                    "login_prompt":any(word in text for word in ("qr", "vincular", "telefone", "phone", "aparelhos conectados")),
                    "account_linked":False,"messages_sent":0}
            print(json.dumps(result,ensure_ascii=False))
            if not result["login_prompt"] or result["connected"]:
                raise RuntimeError("Public login page was not validated.")
        finally:
            await browser.close()


asyncio.run(main())
