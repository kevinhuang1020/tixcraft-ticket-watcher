"""根據 target_date / keyword 從場次列表中篩選符合的場次。"""
import re


def _normalize_date(s):
    if not s:
        return ""
    return re.sub(r"[/\-.]", "", s).strip()


def match_target(games, target_date="", keyword="", exclude_keywords=None):
    """回傳 (matched_game_or_None, candidates)。

    匹配規則：
      - target_date 空 → 不依日期篩
      - target_date 非空 → 比對 game["date"]（YYYY-MM-DD）或 game["date_raw"]
      - keyword 非空 → game 的任意欄位 substring 比對（必須含）
      - exclude_keywords 非空 → 任一字串出現在欄位裡就排除（用來過濾「身心障礙席」、「三星專區」等）
    若篩出 >1 場，回傳第一場、但 candidates 保留全部給 caller 警告用。
    """
    nd_target = _normalize_date(target_date)
    exclude_keywords = exclude_keywords or []

    matched = []
    for g in games:
        if nd_target:
            nd_game = _normalize_date(g.get("date", "") or g.get("date_raw", ""))
            if nd_target not in nd_game and nd_game not in nd_target:
                continue
        hay = " ".join([
            g.get("title", ""),
            g.get("venue", ""),
            g.get("raw_text", ""),
        ])
        if keyword and keyword not in hay:
            continue
        if any(ek and ek in hay for ek in exclude_keywords):
            continue
        matched.append(g)

    if not matched:
        return None, []
    return matched[0], matched
