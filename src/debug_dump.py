"""Dump tixcraft 頁面 HTML 與截圖，方便看實際結構。"""
import sys
from playwright.sync_api import sync_playwright
from scraper import USER_AGENT, game_list_url


def main():
    if len(sys.argv) < 2:
        print("用法: python src/debug_dump.py <event_url_or_id>")
        sys.exit(1)
    arg = sys.argv[1]
    if "://" not in arg:
        arg = f"https://tixcraft.com/activity/detail/{arg}"

    detail_url = arg
    game_url = game_list_url(arg)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="zh-TW", user_agent=USER_AGENT)
        page = ctx.new_page()

        for label, url in [("detail", detail_url), ("game", game_url)]:
            print(f"\n=== {label}: {url} ===")
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                print(f"  status: {resp.status if resp else '?'}")
                print(f"  final url: {page.url}")
                page.wait_for_timeout(2000)
                html = page.content()
                with open(f"debug_{label}.html", "w", encoding="utf-8") as f:
                    f.write(html)
                page.screenshot(path=f"debug_{label}.png", full_page=True)
                print(f"  HTML {len(html)} bytes → debug_{label}.html")
                # title + h1 + 看有沒有 table
                title = page.title()
                print(f"  title: {title}")
                tables = page.query_selector_all("table")
                print(f"  tables: {len(tables)}")
                # 找關鍵字
                for kw in ["立即購票", "已售完", "未開賣", "結束販售", "登記抽選"]:
                    if kw in html:
                        print(f"  contains: {kw}")
            except Exception as e:
                print(f"  ERROR: {e}")

        ctx.close()
        browser.close()


if __name__ == "__main__":
    main()
