"""Helper：列出某個 tixcraft 活動的所有場次與狀態。

用法：
    python src/list_games.py https://tixcraft.com/activity/detail/26_nmixx
    python src/list_games.py 26_nmixx
"""
import sys

from scraper import fetch_event, game_list_url


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    arg = sys.argv[1]
    if "://" not in arg:
        arg = f"https://tixcraft.com/activity/detail/{arg}"

    print(f"[list_games] 抓取 {game_list_url(arg)} ...")
    games = fetch_event(arg, headless=True, debug=True)
    print()
    print(f"找到 {len(games)} 場：")
    print()
    print(f"  {'#':<3} {'日期':<12} {'狀態':<10} 名稱")
    print(f"  {'-'*3} {'-'*12} {'-'*10} {'-'*40}")
    for i, g in enumerate(games, 1):
        date = g.get("date") or g.get("date_raw") or "?"
        title = (g.get("title") or "")[:50]
        print(f"  {i:<3} {date:<12} {g['status']:<10} {title}")


if __name__ == "__main__":
    main()
