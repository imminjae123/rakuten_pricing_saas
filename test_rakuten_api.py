"""
STEP 1 — 楽天市場 商品検索API テストスクリプト
=============================================

目的:
  .env に設定した RAKUTEN_APPLICATION_ID を使って
  楽天 IchibaItem/Search API を呼び出し、
  上位3件の「商品名」と「税込価格」をコンソールに出力する。

使い方:
  1. .env ファイルに RAKUTEN_APPLICATION_ID=あなたのアプリID を記入
  2. pip install httpx python-dotenv
  3. python test_rakuten_api.py
  4. 検索キーワードを入力（例: Nintendo Switch）

APIドキュメント:
  https://webservice.rakuten.co.jp/documentation/ichiba-item-search
"""

import sys
import httpx
from dotenv import load_dotenv
import os

# ── 1. .env ファイルを読み込む ─────────────────────────────────────────────────
load_dotenv()  # rakuten_pricing_saas/.env を自動検索して環境変数に展開する

APP_ID     = os.getenv("RAKUTEN_APPLICATION_ID", "")
ACCESS_KEY = os.getenv("RAKUTEN_ACCESS_KEY", "")

if not APP_ID or APP_ID == "your_rakuten_app_id_here":
    print("=" * 60)
    print("❌ エラー: RAKUTEN_APPLICATION_ID が設定されていません。")
    print()
    print("  .env ファイルを開いて、以下のように記入してください：")
    print("  RAKUTEN_APPLICATION_ID=あなたのアプリID")
    print("  RAKUTEN_ACCESS_KEY=あなたのAccess Key")
    print()
    print("  ※ .env ファイルがない場合は、.env.example をコピーして")
    print("    .env という名前で保存してから編集してください。")
    print("=" * 60)
    sys.exit(1)

# ── 2. APIエンドポイントとパラメーターを設定 ──────────────────────────────────
RAKUTEN_API_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"

def search_items(keyword: str, hits: int = 3) -> None:
    """
    楽天市場で keyword を検索し、上位 hits 件の商品情報を表示する。

    Parameters
    ----------
    keyword : 検索キーワード（例: "Nintendo Switch"）
    hits    : 取得件数（1〜30、デフォルト3）
    """
    params = {
        "applicationId": APP_ID,
        "keyword":       keyword,
        "hits":          hits,          # 取得件数
        "sort":          "-reviewCount", # レビュー数順（人気順の代わり）
        "formatVersion": 2,             # JSON形式 v2（itemsがフラットな配列）
    }

    # Access Key が .env に設定されている場合は Authorization ヘッダーで渡す
    # （2020年以降の新形式アプリは applicationId + Access Key の組み合わせが必要）
    headers = {}
    if ACCESS_KEY:
        import base64
        cred = base64.b64encode(f"{APP_ID}:{ACCESS_KEY}".encode()).decode()
        headers["Authorization"] = f"Basic {cred}"
        # Basic 認証使用時はクエリの applicationId は不要だが念のため残す

    print(f"\n🔍 「{keyword}」で楽天市場を検索中...\n")

    try:
        # httpx.get はデフォルトで10秒タイムアウト
        response = httpx.get(RAKUTEN_API_URL, params=params, headers=headers, timeout=10.0)
        response.raise_for_status()     # 4xx / 5xx はここで例外になる
    except httpx.TimeoutException:
        print("❌ タイムアウトしました。ネットワーク接続を確認してください。")
        return
    except httpx.HTTPStatusError as e:
        # よくあるエラー: 401 = App ID が無効、429 = レートリミット超過
        print(f"❌ API エラー: HTTP {e.response.status_code}")
        if e.response.status_code == 401:
            print("   → Application ID が無効です。楽天 Web Services で確認してください。")
        elif e.response.status_code == 429:
            print("   → リクエスト上限を超えました。少し待ってから再試行してください。")
        else:
            print(f"   → レスポンス: {e.response.text[:200]}")
        return

    data = response.json()

    # ── 3. 結果を解析して表示 ─────────────────────────────────────────────────
    items = data.get("Items", [])

    if not items:
        print("  検索結果が0件でした。別のキーワードを試してください。")
        return

    print(f"{'─' * 60}")
    print(f"  検索結果 上位 {len(items)} 件")
    print(f"{'─' * 60}")

    for i, item in enumerate(items, start=1):
        name      = item.get("itemName", "（名称不明）")
        price     = item.get("itemPrice", 0)          # 税込価格（整数・円）
        shop_name = item.get("shopName", "（店舗名不明）")
        item_url  = item.get("itemUrl", "")

        # 商品名が長い場合は60文字で切り捨て
        display_name = name if len(name) <= 60 else name[:57] + "..."

        print(f"\n  [{i}]  {display_name}")
        print(f"       価格  : ¥{price:,}（税込）")
        print(f"       店舗  : {shop_name}")
        print(f"       URL   : {item_url}")

    print(f"\n{'─' * 60}")
    print(f"  ✅ 取得完了！（合計 {data.get('count', '?')} 件がヒットしました）")
    print(f"{'─' * 60}\n")


# ── 4. メイン処理 ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # コマンドライン引数があればそれをキーワードに使う
    # 例: python test_rakuten_api.py "Nintendo Switch"
    if len(sys.argv) >= 2:
        keyword = " ".join(sys.argv[1:])
    else:
        # 引数がなければ対話式で入力を求める
        keyword = input("検索キーワードを入力してください（例: Nintendo Switch）: ").strip()
        if not keyword:
            keyword = "Nintendo Switch"
            print(f"  （入力なし → デフォルトキーワード「{keyword}」を使用します）")

    search_items(keyword, hits=3)
