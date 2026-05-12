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


def load_state():
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def diff_status(results, prev_state):
    """results: list of dict {name, status, ...}
    回傳 (events, new_state)
    events: list of (result, prev_status, curr_status, kind)
      kind: "became_available" | "became_unavailable" | "config_broken"
    """
    new_state = {}
    events = []
    is_first_run = not prev_state

    for r in results:
        name = r["name"]
        curr = r["status"]
        new_state[name] = curr

        if is_first_run:
            continue

        prev = prev_state.get(name)
        if prev is None:
            if curr == AVAILABLE:
                events.append((r, None, curr, "became_available"))
            continue

        if prev == curr:
            continue

        if curr == AVAILABLE:
            events.append((r, prev, curr, "became_available"))
        elif prev == AVAILABLE:
            events.append((r, prev, curr, "became_unavailable"))
        elif curr == NO_MATCH and prev != NO_MATCH:
            events.append((r, prev, curr, "config_broken"))

    return events, new_state
