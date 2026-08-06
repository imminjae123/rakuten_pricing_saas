"""
Yahoo! Japan Shopping API v3 テストスクリプト
=============================================

目的:
  .env に設定した YAHOO_CLIENT_ID を使って
  Yahoo! ショッピング itemSearch API v3 を呼び出し、
  上位3件の「商品名」と「税込価格」をコンソールに出力する。

使い方:
  1. .env ファイルに YAHOO_CLIENT_ID=あなたのクライアントID を記入
  2. pip install httpx python-dotenv
  3. python test_yahoo_api.py
  4. 検索キーワードを入力（例: Nintendo Switch）

APIドキュメント:
  https://developer.yahoo.co.jp/webapi/shopping/shopping/v3/itemsearch.html
"""

import asyncio
import sys

from dotenv import load_dotenv
import os

# ── 1. .env ファイルを読み込む ─────────────────────────────────────────────────
load_dotenv()

CLIENT_ID = os.getenv("YAHOO_CLIENT_ID", "")

if not CLIENT_ID or CLIENT_ID == "your_yahoo_client_id_here":
    print("=" * 60)
    print("❌ エラー: YAHOO_CLIENT_ID が設定されていません。")
    print()
    print("  .env ファイルを開いて、以下のように記入してください：")
    print("  YAHOO_CLIENT_ID=あなたのクライアントID")
    print()
    print("  ※ .env ファイルがない場合は、.env.example をコピーして")
    print("    .env という名前で保存してから編集してください。")
    print("=" * 60)
    sys.exit(1)

# ── 2. Yahoo! Shopping API クライアントをインポート ────────────────────────────
# app/services/yahoo.py で定義した非同期クライアントを利用する
import httpx


_YAHOO_SEARCH_URL = (
    "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
)


async def search_items(keyword: str, results: int = 3) -> None:
    """
    Yahoo! ショッピングで keyword を検索し、上位 results 件の商品情報を表示する。

    Parameters
    ----------
    keyword : 検索キーワード（例: "Nintendo Switch"）
    results : 取得件数（1〜50、デフォルト3）
    """
    params = {
        "appid":   CLIENT_ID,
        "query":   keyword,
        "results": results,
        "sort":    "-score",   # 関連度順
    }

    print(f"\n🔍 「{keyword}」でYahoo!ショッピングを検索中...\n")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(_YAHOO_SEARCH_URL, params=params)
            response.raise_for_status()
    except httpx.TimeoutException:
        print("❌ タイムアウトしました。ネットワーク接続を確認してください。")
        return
    except httpx.HTTPStatusError as e:
        print(f"❌ API エラー: HTTP {e.response.status_code}")
        if e.response.status_code == 400:
            print("   → リクエストパラメーターが不正です。YAHOO_CLIENT_ID を確認してください。")
        elif e.response.status_code == 403:
            print("   → アクセスが拒否されました。Client ID の権限を確認してください。")
        elif e.response.status_code == 429:
            print("   → リクエスト上限を超えました。少し待ってから再試行してください。")
        else:
            print(f"   → レスポンス: {e.response.text[:200]}")
        return

    data = response.json()

    # ── 3. 結果を解析して表示 ─────────────────────────────────────────────────
    hits = data.get("hits", [])

    if not hits:
        print("  検索結果が0件でした。別のキーワードを試してください。")
        return

    total = data.get("totalResultsAvailable", "?")

    print(f"{'─' * 60}")
    print(f"  検索結果 上位 {len(hits)} 件  （合計 {total} 件ヒット）")
    print(f"{'─' * 60}")

    for i, item in enumerate(hits, start=1):
        name      = item.get("name", "（名称不明）")
        price     = item.get("price", 0)
        shop_name = item.get("seller", {}).get("name", "（店舗名不明）")
        item_url  = item.get("url", "")
        image_url = item.get("image", {}).get("medium", "")

        # 商品名が長い場合は60文字で切り捨て
        display_name = name if len(name) <= 60 else name[:57] + "..."

        print(f"\n  [{i}]  {display_name}")
        print(f"       価格  : ¥{price:,}（税込）")
        print(f"       店舗  : {shop_name}")
        print(f"       URL   : {item_url}")
        if image_url:
            print(f"       画像  : {image_url}")

    print(f"\n{'─' * 60}")
    print(f"  ✅ 取得完了！")
    print(f"{'─' * 60}\n")


# ── 4. メイン処理 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # コマンドライン引数があればそれをキーワードに使う
    # 例: python test_yahoo_api.py "Nintendo Switch"
    if len(sys.argv) >= 2:
        keyword = " ".join(sys.argv[1:])
    else:
        # 引数がなければ対話式で入力を求める
        keyword = input("検索キーワードを入力してください（例: Nintendo Switch）: ").strip()
        if not keyword:
            keyword = "Nintendo Switch"
            print(f"  （入力なし → デフォルトキーワード「{keyword}」を使用します）")

    asyncio.run(search_items(keyword, results=3))
