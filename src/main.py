"""主程式：讀 targets.json → 逐個 scrape → match → diff → notify。"""
import json
import os
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

from scraper import fetch_event
from filter import match_target
from state import (
    load_state, save_state, diff_status,
    AVAILABLE, NO_MATCH, NO_SESSIONS, UNKNOWN,
)
from notifier import notify_events, notify_heartbeat, notify_scrape_failed

TARGETS_PATH = Path(os.getenv("TARGETS_PATH", "targets.json"))
NOTIFY_STATE_PATH = Path("notify_state.json")
HEARTBEAT_INTERVAL = timedelta(hours=8)


def load_targets():
    if not TARGETS_PATH.exists():
        raise FileNotFoundError(f"找不到 {TARGETS_PATH}，請先建立 targets.json")
    return json.loads(TARGETS_PATH.read_text(encoding="utf-8"))


def _load_last_notify_at():
    if not NOTIFY_STATE_PATH.exists():
        return None
    try:
        return datetime.fromisoformat(json.loads(NOTIFY_STATE_PATH.read_text())["last_notify_at"])
    except Exception:
        return None


def mark_notified():
    NOTIFY_STATE_PATH.write_text(json.dumps({"last_notify_at": datetime.now().isoformat()}))


def should_send_heartbeat():
    last = _load_last_notify_at()
    if last is None:
        return True
    return datetime.now() - last >= HEARTBEAT_INTERVAL


def evaluate_target(t):
    """跑單一 target，回傳 result dict（含 status）。"""
    name = t.get("name") or t.get("event_url", "")
    event_url = t["event_url"]
    target_date = t.get("target_date", "")
    keyword = t.get("keyword", "")
    exclude_keywords = t.get("exclude_keywords", [])

    result = {
        "name": name,
        "event_url": event_url,
        "target_date": target_date,
        "keyword": keyword,
        "exclude_keywords": exclude_keywords,
        "status": "unknown",
        "matched_date": None,
        "matched_title": None,
        "all_candidates": [],
    }

    try:
        games, page_ok = fetch_event(event_url, headless=True)
    except Exception as e:
        print(f"[main] scrape 失敗 {name}: {e}")
        traceback.print_exc()
        result["status"] = UNKNOWN
        result["error"] = str(e)
        return result

    print(f"[main] {name} → {len(games)} 場 (page_ok={page_ok})")
    for g in games:
        print(f"  - {g.get('date','?')} {g.get('title','')[:40]} → {g.get('status')}")

    if not page_ok:
        result["status"] = UNKNOWN
        return result

    if not games:
        # 頁面 OK 但 tixcraft 顯示「目前無場次資訊」
        result["status"] = NO_SESSIONS
        return result

    matched, candidates = match_target(games, target_date, keyword, exclude_keywords)
    result["all_candidates"] = [
        {"date": g.get("date"), "title": g.get("title"), "status": g.get("status")}
        for g in candidates
    ]

    if not matched:
        if target_date or keyword:
            result["status"] = NO_MATCH
        else:
            statuses = [g.get("status") for g in games]
            if AVAILABLE in statuses:
                result["status"] = AVAILABLE
                first_avail = next(g for g in games if g.get("status") == AVAILABLE)
                result["matched_date"] = first_avail.get("date")
                result["matched_title"] = first_avail.get("title")
            elif "soldout" in statuses:
                result["status"] = "soldout"
            elif statuses:
                result["status"] = statuses[0]
            else:
                result["status"] = NO_SESSIONS
        return result

    if len(candidates) > 1:
        print(f"[main] ⚠️ {name} 篩出 {len(candidates)} 場，使用第一場：{matched.get('date')} {matched.get('title','')[:40]}")

    result["status"] = matched.get("status", "unknown")
    result["matched_date"] = matched.get("date")
    result["matched_title"] = matched.get("title")
    result["buy_url"] = matched.get("buy_href") or ""
    return result


def main():
    try:
        targets = load_targets()
    except Exception as e:
        print(f"[main] 讀取 targets.json 失敗: {e}")
        sys.exit(1)

    if not targets:
        print("[main] targets.json 是空的，沒事做")
        return

    results = []
    for t in targets:
        results.append(evaluate_target(t))

    prev = load_state()
    events, new_state = diff_status(results, prev)
    save_state(new_state)

    if events:
        kinds = [e[3] for e in events]
        print(f"[main] 推播：{len(events)} 個事件 {kinds}")
        notify_events(events, results)
        mark_notified()
        return

    print("[main] 無事件，靜默")


if __name__ == "__main__":
    main()
