# tixcraft-ticket-watcher

監控 tixcraft 指定活動指定場次的票況變化（售完/未開賣 → 立即購票），透過 LINE 推播通知。

仿照 `ctbc-ticket-watcher` 架構，但 tixcraft 的選區頁有反爬蟲 + 排隊系統，所以本工具**只看場次層級狀態**（整場有票 / 沒票），不細到區域。

## 設定

1. 複製 `.env.example` 為 `.env`，填入 LINE token。
2. 編輯 `targets.json`，每個要監控的場次一筆：
   - `name`：自訂名稱（通知會顯示）
   - `event_url`：tixcraft 活動詳情頁 URL
   - `target_date`：YYYY-MM-DD 或 YYYY/MM/DD，留空表示「任一場有票就通知」
   - `keyword`：同一天有多場時用來 disambiguate 的子字串（選填）
3. 不知道日期就先跑 `python src/list_games.py <event_url>` 看有哪些場次。

## 本機跑

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

# 列出某活動所有場次
python src/list_games.py https://tixcraft.com/activity/detail/26_nmixx

# 跑一次主程式
PYTHONPATH=src python src/main.py
```

## 自動排程

GitHub Actions 每 10 分鐘跑一次。設定 secrets：`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_USER_ID`。
