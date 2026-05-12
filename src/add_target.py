"""互動式新增監控目標到 targets.json。

用法:
    python src/add_target.py <event_url_or_id>

例:
    python src/add_target.py https://tixcraft.com/activity/detail/26_nmixx
    python src/add_target.py 26_nmixx
"""
import json
import os
import sys
from pathlib import Path

from scraper import fetch_event, event_id_from_url

TARGETS_PATH = Path(os.getenv("TARGETS_PATH", "targets.json"))


def load_targets():
    if not TARGETS_PATH.exists():
        return []
    return json.loads(TARGETS_PATH.read_text(encoding="utf-8"))


def save_targets(ts):
    TARGETS_PATH.write_text(
        json.dumps(ts, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def prompt(msg, default=""):
    s = input(f"{msg}{f' [{default}]' if default else ''}: ").strip()
    return s or default


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    arg = sys.argv[1]
    if "://" not in arg:
        arg = f"https://tixcraft.com/activity/detail/{arg}"

    print(f"[add] 抓取 {arg} 的場次列表 ...")
    try:
        games, page_ok = fetch_event(arg, headless=True)
    except Exception as e:
        print(f"[add] 抓取失敗: {e}")
        games, page_ok = [], False

    print(f"[add] page_ok={page_ok}, 找到 {len(games)} 場")
    print()
    if games:
        print(f"  {'#':<3} {'日期':<12} {'狀態':<10} 名稱")
        print(f"  {'-'*3} {'-'*12} {'-'*10} {'-'*50}")
        for i, g in enumerate(games, 1):
            date = g.get("date") or g.get("date_raw") or "?"
            title = (g.get("title") or "")[:50]
            print(f"  {i:<3} {date:<12} {g['status']:<10} {title}")
        print(f"  {'A':<3} {'(any)':<12} 任一場有票就通知")
    else:
        print("  （目前 0 場，可以直接手動填日期）")
    print()

    pick = prompt("選哪一場？輸入 # / A / 自訂日期 YYYY-MM-DD", "A")
    target_date = ""
    suggested_name_part = ""
    if pick.upper() == "A":
        target_date = ""
    elif pick.isdigit() and 1 <= int(pick) <= len(games):
        g = games[int(pick) - 1]
        target_date = g.get("date") or ""
        suggested_name_part = (g.get("title") or "")[:20]
    else:
        target_date = pick  # 視為使用者直接輸入的日期

    keyword = prompt("關鍵字（同一天有多場時用來 disambiguate，可留空）", "")

    eid = event_id_from_url(arg) or "event"
    default_name = f"{eid}"
    if target_date:
        default_name += f" {target_date}"
    if suggested_name_part:
        default_name = f"{suggested_name_part}"
    name = prompt("此目標的顯示名稱", default_name)

    new_entry = {
        "name": name,
        "event_url": f"https://tixcraft.com/activity/detail/{eid}",
        "target_date": target_date,
        "keyword": keyword,
    }

    targets = load_targets()
    # 同名警告
    for t in targets:
        if t.get("name") == name:
            ans = prompt(f"已有同名目標 {name!r}，覆蓋？(y/N)", "N")
            if ans.lower() != "y":
                print("[add] 取消")
                return
            targets = [t for t in targets if t.get("name") != name]
            break

    targets.append(new_entry)
    save_targets(targets)
    print()
    print(f"[add] ✅ 已加入 targets.json：")
    print(json.dumps(new_entry, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
