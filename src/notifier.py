"""LINE Messaging API 推播。"""
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
USER_ID = os.getenv("LINE_USER_ID")
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
LINE_MAX_UTF16 = 4800


STATUS_LABEL = {
    "available": "🟢 立即購票",
    "soldout": "🔴 已售完",
    "not_yet": "⚪ 未開賣",
    "ended": "⚫ 結束販售",
    "unknown": "❓ 狀態未知",
    "no_match": "⚠️ 找不到符合場次",
    "no_sessions": "⚫ 目前無場次",
}


def _utf16_len(s):
    return len(s.encode("utf-16-le")) // 2


def _split_chunks(text, size=LINE_MAX_UTF16):
    if _utf16_len(text) <= size:
        return [text]
    chunks, buf, buf_len = [], [], 0
    for line in text.split("\n"):
        line_len = _utf16_len(line) + 1
        if line_len > size:
            if buf:
                chunks.append("\n".join(buf))
                buf, buf_len = [], 0
            s = line
            while s:
                cut = size
                while _utf16_len(s[:cut]) > size and cut > 0:
                    cut -= 1
                chunks.append(s[:cut])
                s = s[cut:]
            continue
        if buf_len + line_len > size:
            chunks.append("\n".join(buf))
            buf, buf_len = [], 0
        buf.append(line)
        buf_len += line_len
    if buf:
        chunks.append("\n".join(buf))
    return chunks


def send_line_message(text, quiet=False):
    if not TOKEN or not USER_ID:
        print("[notifier] 未設定 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID，跳過推播")
        print("---")
        print(text)
        print("---")
        return False
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}",
    }
    ok = True
    for chunk in _split_chunks(text):
        payload = {"to": USER_ID, "messages": [{"type": "text", "text": chunk}]}
        try:
            r = requests.post(LINE_PUSH_URL, headers=headers, json=payload, timeout=10)
            if r.status_code != 200:
                print(f"[notifier] 推播失敗 {r.status_code}: {r.text}")
                ok = False
            elif not quiet:
                print("[notifier] 推播成功")
        except Exception as e:
            print(f"[notifier] 推播異常: {e}")
            ok = False
    return ok


def _result_line(r):
    label = STATUS_LABEL.get(r["status"], r["status"])
    date = r.get("matched_date") or r.get("target_date") or "(未指定日期)"
    title = r.get("matched_title", "")
    line = f"  {label}  {date}"
    if title:
        line += f"  {title}"
    return line


def notify_events(events, all_results):
    """events: [(result, prev, curr, kind)] —— became_<curr_status>，任何狀態變化都推。
    有票 (became_available) 以 🚨 顯眼方式呈現；其他變化用 📋 一般風格。
    """
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
    return send_line_message("\n".join(lines))


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
