"""Telegram Bot API 推播。"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

import gitops

load_dotenv()

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TG_MAX_CHARS = 4000  # 上限 4096，留餘裕

ANNOUNCED_PATH = Path("announced.json")
DEDUP_COOLDOWN = timedelta(minutes=30)


STATUS_LABEL = {
    "available": "🟢 立即購票",
    "soldout": "🔴 已售完",
    "not_yet": "⚪ 未開賣",
    "ended": "⚫ 結束販售",
    "unknown": "❓ 狀態未知",
    "no_match": "⚠️ 找不到符合場次",
    "no_sessions": "⚫ 目前無場次",
}


def _split_chunks(text, size=TG_MAX_CHARS):
    if len(text) <= size:
        return [text]
    chunks, buf, buf_len = [], [], 0
    for line in text.split("\n"):
        line_len = len(line) + 1
        if line_len > size:
            if buf:
                chunks.append("\n".join(buf))
                buf, buf_len = [], 0
            s = line
            while s:
                chunks.append(s[:size])
                s = s[size:]
            continue
        if buf_len + line_len > size:
            chunks.append("\n".join(buf))
            buf, buf_len = [], 0
        buf.append(line)
        buf_len += line_len
    if buf:
        chunks.append("\n".join(buf))
    return chunks


def send_telegram_message(text, quiet=False):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("[notifier] 未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，跳過推播")
        print("---")
        print(text)
        print("---")
        return False
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    ok = True
    for chunk in _split_chunks(text):
        payload = {
            "chat_id": TG_CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code != 200:
                print(f"[notifier] 推播失敗 {r.status_code}: {r.text}")
                ok = False
            elif not quiet:
                print("[notifier] 推播成功")
        except Exception as e:
            print(f"[notifier] 推播異常: {e}")
            ok = False
    return ok


# 舊名相容：呼叫 send_line_message 仍可運作
send_line_message = send_telegram_message


def _result_line(r):
    label = STATUS_LABEL.get(r["status"], r["status"])
    date = r.get("matched_date") or r.get("target_date") or "(未指定日期)"
    title = r.get("matched_title", "")
    line = f"  {label}  {date}"
    if title:
        line += f"  {title}"
    return line


def _load_announced():
    if not ANNOUNCED_PATH.exists():
        return {}
    try:
        return json.loads(ANNOUNCED_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_announced(d):
    ANNOUNCED_PATH.write_text(
        json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _dedup_filter(events):
    """過濾掉 30 分鐘內已推過的相同 (name, curr_status) 事件。
    回傳 (kept, announced_dict_to_save)。"""
    announced = _load_announced()
    now = datetime.now()
    kept = []
    for e in events:
        r, prev, curr, _ = e
        key = f"{r['name']}::{curr}"
        prev_at_str = announced.get(key)
        if prev_at_str:
            try:
                prev_at = datetime.fromisoformat(prev_at_str)
                if now - prev_at < DEDUP_COOLDOWN:
                    print(f"[dedup] 跳過 {key}（{(now - prev_at).total_seconds():.0f}s 前已推）")
                    continue
            except Exception:
                pass
        kept.append(e)
        announced[key] = now.isoformat(timespec="seconds")
    return kept, announced


def notify_events(events, all_results):
    """events: [(result, prev, curr, kind)] —— became_<curr_status>，任何狀態變化都推。
    有票 (became_available) 以 🚨 顯眼方式呈現；其他變化用 📋 一般風格。
    去重：同 (name, curr_status) 在 30 分鐘內只推一次（透過 announced.json + git 共享）。
    """
    events, announced = _dedup_filter(events)
    if not events:
        print("[notify] 所有事件都被去重 — 跳過推播")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    became_avail = [e for e in events if e[2] == "available"]
    others = [e for e in events if e[2] != "available"]

    lines = []
    if became_avail:
        lines.append(f"🚨 tixcraft 有票了！（{len(became_avail)} 場）  {now}")
        lines.append("")
        for r, prev, curr, _ in became_avail:
            lines.append(f"▶ {r['name']}")
            lines.append(_result_line(r))
            lines.append(f"  🔗 {r.get('event_url','')}")
            lines.append("")

    if others:
        lines.append(f"📋 tixcraft 場次狀態更新  {now}")
        lines.append("")
        for r, prev, curr, _ in others:
            prev_lbl = STATUS_LABEL.get(prev, prev or "(初次)")
            curr_lbl = STATUS_LABEL.get(curr, curr)
            lines.append(f"▶ {r['name']}")
            lines.append(f"   {prev_lbl}  →  {curr_lbl}")
            lines.append("")

    lines.append("─── 目前監控狀態 ───")
    for r in all_results:
        lines.append(f"  {r['name']}: {STATUS_LABEL.get(r['status'], r['status'])}")
    lines.append("")
    if became_avail:
        lines.append("⚠️ 請手動前往購票，本程式不會自動下單")
    ok = send_line_message("\n".join(lines))
    if ok:
        _save_announced(announced)
        gitops.commit_push(["announced.json"], "dedup: announced events")
    return ok


def notify_heartbeat(all_results):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"💓 tixcraft 監控心跳  {now}", ""]
    for r in all_results:
        lines.append(f"▶ {r['name']}")
        lines.append(_result_line(r))
        if r.get("event_url"):
            lines.append(f"  🔗 {r['event_url']}")
        lines.append("")
    lines.append("⏰ 8 小時後若仍無異動會再次提醒")
    return send_line_message("\n".join(lines))


def notify_scrape_failed(error):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = f"❌ tixcraft 監控異常  {now}\n\n{error}\n\n下次排程會再試。"
    return send_line_message(text)
