# B2B SaaS 要件定義書：Yahoo! ショッピング 競合価格モニタリング＆自動価格対応ソリューション

## 1. プロジェクト概要
* **プロジェクト名:** Yahoo! Shopping Dynamic Pricing Tracker (仮称)
* **目的:** 日本のYahoo! ショッピングに出店しているセラー（テナント）が、競合店舗の価格変動をリアルタイムまたはバッチ処理でモニタリングし、事前定義したビジネスルール（Rule）に従って自社商品の最適販売価格を自動算出し対応できるように支援するB2B SaaSプラットフォーム。
* **学習目標 (個人プロジェクトの観点):**
  - **Multi-Tenancy:** セラー（顧客企業）ごとのデータ隔離およびスキーマ/Row-Levelセキュリティ設計
  - **Rule Engine:** 動的ビジネス条件のパースおよびドメイン計算エンジンの実装
  - **Data Pipeline:** 外部APIのRate Limitを考慮した大規模データ収集および状態同期
  - **Audit Logging:** センシティブなトランザクション（価格変動、ルール修正）の不可変（Immutable）履歴管理

---

## 2. システムアーキテクチャおよび技術スタック (無料インフラ中心)

費用を最小化（0円）しながら、商用サービスレベルのバックエンドアーキテクチャを経験できるように構成します。

### 2.1. Backend (API & ビジネスロジック)
* **言語 & フレームワーク:** Python 3 + FastAPI（確定）
  * *非同期処理 (Async) およびデータハンドリングが多い点を考慮し、Python + FastAPIの組み合わせを採用します。*
* **ORM:** SQLAlchemy 2.0 (async flavour、`asyncpg` ドライバー使用)
* **API規格:** RESTful API (`/api/v1/...`)

### 2.2. Frontend (FastAPI統合型 — ビルド環境なし)

> **方針:** Node.js / React などの独立したフロントエンドビルド環境を排除し、FastAPIサーバー1プロセスでAPIとUIの両方を提供します。0円インフラ（Render.com 等）上で単一 dyno としてデプロイ・運用できます。

| レイヤー | 採用技術 | 選定理由 |
|---|---|---|
| **テンプレートエンジン** | **Jinja2** (FastAPI 内蔵 `Jinja2Templates`) | サーバーサイドHTML生成。`package.json`・`node_modules`・ビルドコマンドが不要 |
| **動的UI / 非同期通信** | **HTMX** (CDN) | `hx-get` / `hx-post` 属性のみでSPA的な部分更新を実現。カスタムJSをほぼ書かない |
| **CSSフレームワーク** | **Tailwind CSS** (CDN `<script>` タグ) | CDN利用でビルド設定ゼロ。Node.js不要のままユーティリティCSSが使える |
| **グラフ描画** | **Chart.js** (CDN) | 競合価格変動タイムライン・推奨価格トレンドの描画に使用 |

* HTMLページルートは `/ui/...` に配置し、JSONエンドポイント (`/api/v1/...`) と完全に分離する
* HTMX部分更新レスポンスはHTMLフラグメントのみを返す（フルページレスポンス禁止）
* JWT認証はUI向けに `httpOnly` Cookie で管理する（`localStorage` やURLパラメーターへのトークン露出禁止）
* Chart.js用データ取得は `GET /api/v1/histories/...` への最小限の `<script>` ブロックのみ許可する
* `package.json`・`node_modules/`・Webpack/Vite等のビルド設定ファイルはリポジトリに追加しない

### 2.3. Database & Caching
* **Relational DB:** PostgreSQL (無料ホスティング: Neon または Supabase)
  * RLS (Row-Level Security) および JSONB型を活用したルールエンジンの構築に最適化
* **In-Memory Cache:** Redis (無料ホスティング: Upstash)
  * Yahoo! Shopping APIレスポンスのキャッシング、Rate Limit制御、非同期タスクキューの状態管理

### 2.4. Data Pipeline & Worker
* **バッチスケジューラ:** GitHub Actions (毎日/毎時 定期クローリングのトリガー) または Celery/APScheduler
* **メッセージキュー (非同期):** Redis Queue (RQ) または Celery (バックグラウンドでのセラー別ルール評価および通知送信処理)

### 2.5. 外部API連携
* **データ収集:** Yahoo! Japan Shopping API v3 itemSearch (`https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch`)
* **通知送信:** LINE Messaging API (過去最安値更新時、対応価格算出時にセラーへプッシュ通知)

### 2.6. インフラデプロイ (Hosting)
* **サーバーデプロイ:** Render.com, Fly.io, または Railway (Free Tier)
* **デプロイ単位:** FastAPI 単一プロセス（APIサーバー + UIサーバーを兼任）

---

## 3. 機能要件 (Functional Requirements)

### 3.1. マルチテナント (Tenant) およびアカウント管理
* **F-1. 店舗 (Tenant) 登録:** セラーは自社のショップ情報 (Shop Code等) を登録してテナントを作成する。
* **F-2. スタッフの役割ベースアクセス制御 (RBAC):**
  * `OWNER`: テナント内の全権限 (決済、ルール修正、アカウント追加)
  * `MANAGER`: 商品マッピングおよびルール設定権限
  * `VIEWER`: ダッシュボードおよびレポート閲覧権限のみ付与

### 3.2. 商品マッピングおよび原価管理
* **F-3. 自社商品登録:** モニタリング対象の自社商品情報、**原価 (Cost)**、**最小保証マージン額/率**を登録する。(※該当情報はテナント内でのみ厳重に保護される)
* **F-4. 競合商品マッピング:** 自社商品1件に対し、モニタリング対象の競合商品 (Yahoo! Shopping Item Code) を1:Nでマッピングする。

### 3.3. 動的価格設定ルールエンジン (Rule Engine)
* **F-5. 条件付きルール (Rule) 作成:** セラーはGUI (またはJSON形式) で価格対応条件を自由に構成できる。
  * *条件例:* 「マッピングされた競合店舗のうち最安値より10円安く設定する。」
  * *制約例:* 「ただし、変更後のマージンが最小保証マージン額 (500円) 未満となる場合は価格を下げず、防衛価格 (原価 + 500円) に固定する。」
* **F-6. ルール評価シミュレーション:** ルールを保存する前に、仮想の競合価格を入力して対応価格が正しく計算されるかを事前にシミュレーションできる。

### 3.4. モニタリングパイプライン (Data Pipeline)
* **F-7. 定期価格モニタリング:** システムは1時間/1日周期でYahoo! Shopping APIを呼び出し、登録された競合商品の現在価格を更新する。
* **F-8. Rate Limiting 防御ロジック:** Yahoo! Shopping APIの呼び出し制限を超えないよう、トークンバケット (Token Bucket) や Sleep ベースの Throttling 処理をパイプラインに実装する。

### 3.5. 通知および履歴管理 (Notification & Audit Logging)
* **F-9. リアルタイム価格対応通知:** パイプラインがルールエンジンを通して新しい「推奨販売価格」を導き出した場合、即座に該当セラーのLINEメッセージへ通知を送信する。
* **F-10. 監査ログ (Audit Log) 提供:** 誰が・いつルールを変更したか、システムがどのような根拠 (競合4,500円 -> ルール#2発動 -> 4,490円算出) で価格を推奨したかをタイムライン形式の不可変ログとして提供する。

---

## 4. 非機能要件 (Non-Functional Requirements)

* **N-1. データ隔離セキュリティ:** すべてのデータ照会および操作APIは、現在認証されているユーザーの `tenant_id` に基づいて動作し、他店舗の原価や設定ルールが漏洩しないようにする。
* **N-2. トランザクション整合性:** 価格推奨履歴の保存と通知のキュー積載処理は1つのトランザクションとしてまとめ、原子性 (Atomicity) を保証する。
* **N-3. Caching:** 変更の少ないカテゴリー情報やテナントのポリシーメタデータはRedisにキャッシングし、DBクエリの負荷を最小化する。

---

## 5. データベースモデリング案 (Key Entities)

* `Tenants`: ショップ情報およびテナント識別子
* `Users`: テナントに所属するスタッフアカウントおよび権限 (Role)
* `My_Products`: 自社商品リストおよび機密情報 (原価、最小マージンなど)
* `Competitor_Products`: Yahoo! Shopping上でモニタリングする他社商品情報
* `Product_Mappings`: `My_Products` と `Competitor_Products` を接続する多対多/1対多ブリッジテーブル
* `Pricing_Rules`: 特定の商品やカテゴリーに適用されるルール (JSONBカラムでの条件式保存を推奨)
* `Price_Histories`: バッチで収集された競合および自社商品の時間経過に伴う価格変動時系列スナップショット
* `Audit_Logs`: ユーザーのシステム操作およびルールエンジン発動結果のログ (Append-Only)

---

## 6. Yahoo! Shopping API v3 itemSearch 連携仕様

### 6.1. エンドポイント
```
GET https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch
```

### 6.2. 認証
* `appid` クエリパラメータに `YAHOO_CLIENT_ID` を指定
* OAuth不要 (itemSearch は読み取り専用API)

### 6.3. 主要リクエストパラメータ
| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `appid` | string | ✓ | Yahoo! デベロッパーネットワークで発行されたClient ID |
| `query` | string | ✓ | 検索キーワード |
| `results` | int | | 取得件数 (1-50、デフォルト10) |
| `sort` | string | | ソート順 (`-price` 価格降順, `+price` 価格昇順, `-score` 関連度順) |

### 6.4. レスポンス構造 (抜粋)
```json
{
  "hits": [
    {
      "name": "商品名",
      "price": 12800,
      "url": "https://store.shopping.yahoo.co.jp/...",
      "code": "store-abc:item-12345",
      "seller": {
        "name": "ショップ名",
        "url": "https://store.shopping.yahoo.co.jp/store-abc/"
      },
      "image": {
        "medium": "https://item-shopping.c.yimg.jp/.../image.jpg"
      }
    }
  ],
  "totalResultsReturned": 10,
  "totalResultsAvailable": 1234
}
```

### 6.5. Rate Limit
* 公式ドキュメントで明示的な制限は公表されていないが、短時間の大量リクエストは制限される可能性がある
* Token Bucket アルゴリズムで1秒あたり1-2リクエストを目安に制御する

### 6.6. 実装クライアント
* `app/services/yahoo.py` — `YahooShoppingClient` (async context manager)
* `httpx.AsyncClient` ベースで非同期HTTP通信
* Pydantic v2 スキーマで応答を厳密にパース

---

## 7. API Reference

| Developer Portal | URL |
|---|---|
| Yahoo! JAPAN デベロッパーネットワーク | https://developer.yahoo.co.jp/ |
| itemSearch API v3 ドキュメント | https://developer.yahoo.co.jp/webapi/shopping/shopping/v3/itemsearch.html |
