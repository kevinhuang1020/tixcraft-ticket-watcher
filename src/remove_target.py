"""從 targets.json 移除監控目標。

用法:
    python src/remove_target.py              # 互動式選號移除
    python src/remove_target.py "目標名稱"    # 直接指定 name 移除
"""
import json
import os
import sys
from pathlib import Path

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


def main():
    targets = load_targets()
    if not targets:
        print("[remove] targets.json 是空的，沒東西可移")
        return

    if len(sys.argv) >= 2:
        name = sys.argv[1]
        new = [t for t in targets if t.get("name") != name]
        if len(new) == len(targets):
            print(f"[remove] 找不到 name={name!r}")
            sys.exit(1)
        save_targets(new)
        print(f"[remove] ✅ 已移除 {name!r}（剩 {len(new)} 個）")
        return

    # 互動模式
    print(f"目前 {len(targets)} 個目標：")
    print(f"  {'#':<3} {'name':<30} {'date':<12} keyword")
    print(f"  {'-'*3} {'-'*30} {'-'*12} {'-'*15}")
    for i, t in enumerate(targets, 1):
        n = (t.get("name") or "")[:30]
        d = t.get("target_date") or "(any)"
        k = t.get("keyword") or ""
        print(f"  {i:<3} {n:<30} {d:<12} {k}")
    print()

    pick = input("移除哪一個？輸入 # 或空白取消: ").strip()
    if not pick:
        print("[remove] 取消")
        return
    if not pick.isdigit() or not (1 <= int(pick) <= len(targets)):
        print("[remove] 編號無效")
        sys.exit(1)
    idx = int(pick) - 1
    removed = targets.pop(idx)
    save_targets(targets)
    print(f"[remove] ✅ 已移除 {removed.get('name')!r}（剩 {len(targets)} 個）")


if __name__ == "__main__":
    main()
