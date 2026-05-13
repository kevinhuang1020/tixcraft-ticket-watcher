"""模擬「became_available」事件，發一則測試 LINE 訊息。

用法：
    PYTHONPATH=src python src/test_notify.py
"""
import json
from pathlib import Path

from notifier import notify_events


def main():
    # 從 targets.json 取第一筆當測試對象
    targets = json.loads(Path("targets.json").read_text(encoding="utf-8"))
    if not targets:
        print("targets.json 是空的，無法測試")
        return
    t = targets[0]

    fake_result = {
        "name": f"[TEST] {t['name']}",
        "event_url": t["event_url"],
        "target_date": t.get("target_date", ""),
        "keyword": t.get("keyword", ""),
        "status": "available",
        "matched_date": t.get("target_date", "2026-07-11"),
        "matched_title": "（測試訊息，請忽略）",
    }
    fake_event = (fake_result, "soldout", "available", "became_available")
    print("[test] 推一則模擬通知到 LINE group...")
    notify_events([fake_event], [fake_result])


if __name__ == "__main__":
    main()
