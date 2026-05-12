"""tixcraft scraper（Playwright）。

只看「場次層級」狀態 —— 不細到區域，也不嘗試突破排隊系統。

URL 結構：
  /activity/detail/{event_id}   活動介紹頁
  /activity/game/{event_id}     場次列表頁（這是我們要抓的）

場次列表頁通常是一張 table，每 row 一個場次：
  日期/時間 | 名稱 | 地點 | 狀態按鈕（立即購票 / 已售完 / 未開賣 / 結束販售）
"""
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def event_id_from_url(url):
    m = re.search(r"/activity/(?:detail|game|info)/([^/?#]+)", url)
    return m.group(1) if m else None


def game_list_url(event_url):
    eid = event_id_from_url(event_url)
    if not eid:
        return event_url
    return f"https://tixcraft.com/activity/game/{eid}"


def classify_status(text, has_buy_button=False):
    """從整列文字判斷狀態。

    has_buy_button: 是否找到一個 data-href 指向 /ticket/area/ 的按鈕。tixcraft 用
    JS 切換按鈕顯示，所以光看文字會把「立即訂購」+「選購一空」同時抓到。
    按鈕的 data-href 才是真正可信的「可購」訊號。
    """
    t = text or ""
    if has_buy_button:
        return "available"
    if "立即購票" in t or "立即訂購" in t:
        # 沒有 data-href 但有按鈕文字 — 保守視為 available
        return "available"
    if "結束販售" in t or "已結束" in t or "販售結束" in t:
        return "ended"
    if "選購一空" in t or "已售完" in t or "售完" in t or "完售" in t:
        return "soldout"
    if "未開賣" in t or "尚未開賣" in t or "即將開賣" in t or "尚未開放" in t:
        return "not_yet"
    if "登記抽選" in t or "登記抽" in t or "抽選" in t:
        return "not_yet"
    return "unknown"


def parse_date_from_text(text):
    """從場次文字抓 YYYY-MM-DD。盡量寬鬆。"""
    if not text:
        return None
    m = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", text)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        try:
            return datetime(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def fetch_games(page, event_url, debug=False):
    """回傳該活動所有場次的 list of dict {date, title, venue, status, raw_text}。"""
    url = game_list_url(event_url)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector("#gameList tbody tr", timeout=15000)
    except Exception:
        # 沒有 #gameList — 可能還沒有上架場次，回空 list
        if debug:
            print(f"[scraper] {url} → 找不到 #gameList tbody tr")
        return []
    page.wait_for_timeout(500)

    rows = page.evaluate(
        """() => {
            const out = [];
            const trs = document.querySelectorAll('#gameList tbody tr');
            for (const tr of trs) {
                const tds = Array.from(tr.querySelectorAll('td'));
                if (tds.length < 2) continue;
                const cells = tds.map(td => (td.textContent || '').replace(/\\s+/g, ' ').trim());
                // 找 data-href 指向 /ticket/area/ 的可購按鈕
                const buyBtn = tr.querySelector('[data-href*="/ticket/area/"]');
                out.push({
                    cells: cells,
                    text: (tr.textContent || '').replace(/\\s+/g, ' ').trim(),
                    has_buy_button: !!buyBtn,
                    buy_href: buyBtn ? buyBtn.getAttribute('data-href') : null,
                    data_key: tr.getAttribute('data-key'),
                });
            }
            return out;
        }"""
    )

    if debug:
        print(f"[scraper] {url} → {len(rows)} rows")
        for r in rows[:10]:
            print(f"  [{r.get('data_key')}] buy={r.get('has_buy_button')} cells={r['cells']}")

    games = []
    for r in rows:
        cells = r["cells"]
        full_text = r["text"]
        if not full_text:
            continue
        status = classify_status(full_text, has_buy_button=r.get("has_buy_button", False))

        date_iso = None
        date_cell = ""
        for c in cells:
            d = parse_date_from_text(c)
            if d and not date_iso:
                date_iso = d
                date_cell = c
                break

        # title / venue：找不是日期、且不是按鈕狀態文字的欄位
        non_date_cells = [c for c in cells if c and c != date_cell]
        # 過濾掉純狀態文字
        title_cell = ""
        venue_cell = ""
        for c in non_date_cells:
            sc = classify_status(c)
            if sc == "unknown" and len(c) > 1:
                if not title_cell:
                    title_cell = c
                elif not venue_cell:
                    venue_cell = c

        games.append({
            "date": date_iso,
            "date_raw": date_cell,
            "title": title_cell,
            "venue": venue_cell,
            "status": status,
            "data_key": r.get("data_key"),
            "buy_href": r.get("buy_href"),
            "raw_text": full_text[:300],
        })
    return games


def fetch_event(event_url, headless=True, debug=False):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(locale="zh-TW", user_agent=USER_AGENT)
        page = ctx.new_page()
        try:
            return fetch_games(page, event_url, debug=debug)
        finally:
            ctx.close()
            browser.close()
