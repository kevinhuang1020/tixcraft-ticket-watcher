"""State 管理：避免重複通知。

key   = target name（targets.json 裡的 name）
value = status string：
  "available"  立即購票
  "soldout"    已售完
  "not_yet"    未開賣
  "ended"      結束販售
  "unknown"    抓不到狀態
  "no_match"   日期/keyword 篩不到任何場次（守護用）

通知規則：
  - 第一次跑（state 空）：不通知，只 snapshot
  - prev != "available" 且 curr == "available"  → 通知「有票了」
  - prev == "available" 且 curr != "available"  → 通知「售完/下架了」
  - "no_match" 狀態變化 → 通知（讓使用者知道設定錯了）
"""
import json
import os
from pathlib import Path

STATE_PATH = Path(os.getenv("STATE_PATH", "state.json"))

AVAILABLE = "available"
SOLDOUT = "soldout"
NOT_YET = "not_yet"
ENDED = "ended"
UNKNOWN = "unknown"
NO_MATCH = "no_match"
NO_SESSIONS = "no_sessions"  # tixcraft 顯示「目前無場次資訊」


def load_state():
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


_REAL_STATUSES = {AVAILABLE, SOLDOUT, NOT_YET, ENDED}


def diff_status(results, prev_state):
    """results: list of dict {name, status, ...}
    回傳 (events, new_state)
    events: list of (result, prev_status, curr_status, kind)
      kind = f"became_{curr_status}"  e.g. "became_available", "became_soldout"

    策略：任何狀態變化都推（跟 ctbc 一樣）。
    防呆：當 curr 是 UNKNOWN（scraper 抓壞）且 prev 是真實狀態 → 保留 prev、靜默
    """
    new_state = {}
    events = []
    is_first_run = not prev_state

    for r in results:
        name = r["name"]
        curr = r["status"]
        prev = prev_state.get(name)

        if curr == UNKNOWN and prev in _REAL_STATUSES:
            print(f"[state] ⚠️ {name} 抓到 unknown，保留 prev={prev}")
            new_state[name] = prev
            r["status"] = prev
            continue

        new_state[name] = curr

        if is_first_run:
            continue

        if prev == curr:
            continue

        # 新目標（prev=None）：只有變 available 才推
        if prev is None:
            if curr == AVAILABLE:
                events.append((r, prev, curr, f"became_{curr}"))
            continue

        # 已存在的目標：任何變化都推
        events.append((r, prev, curr, f"became_{curr}"))

    return events, new_state
