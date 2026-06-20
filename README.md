# 毎日ニュースメモ → LINE 送信ツール（汎用）

設定ファイル（プロフィール）を差し替えるだけで、ジャンルを変えて使える
「毎日リサーチ → LINE 送信」ツール。本運用中（毎日 20:00 JST）。

2系統のパイプラインを同居:
- **news** … Web調査ベースの毎日ニュースメモ（`/news` skill）
- **youtube-stocks** … 株YouTube動画の字幕から銘柄＋見立てを抽出（`/youtube-stocks` skill）
- **disclosure-events** … 全銘柄の株主優待変更をAPIから検出して通知

どちらも「LLMで本文生成 → `message.txt` → `send_line.py` で送信」を共有する。

## 構成

| ファイル | 役割 |
|---|---|
| `.agents/skills/news/SKILL.md` | `/news <profile>` skill。調査〜`message.txt`生成の指示本体 |
| `configs/*.json` | プロフィール。テーマ・優先ソース・出力構成を定義（**ここを編集して方向性を変える**） |
| `send_line.py` | LINE Messaging API push 送信。`.env` または環境変数から認証情報を読む |
| `send_disclosure_events.py` | 未通知の株主優待イベントを取得・整形・送信 |
| `run_disclosure_events.ps1` | 優待イベント通知の定期実行ランナー |
| `message.txt` | 生成された送信本文（毎回上書き） |
| `.env` | `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_USER_ID`（gitignore 済み・コミットしない） |
| `.env.example` | キー名のテンプレート |

## ニュースの方向性を変える（3レイヤー）

`configs/<profile>.json` を編集：

- `themes` … 何を調べるか（調査軸）
- `priority_sources_A` / `_B` … どこを信頼するか（A=一次情報優先）
- `sections` … どう届けるか（セクション名・件数・項目）
- `impact_labels` … 影響分類のラベル
- `rules` … 守らせる方針（出典必須・断定回避 等）
- `title` / `schedule_jst` / `format` … タイトル・送信時刻・体裁

## プロフィールの追加

1. 既存（`configs/market.json`）をコピー → `configs/<新名>.json`
2. `profile` / `title` / `themes` / sources / sections を書き換え
3. 実行時にどのプロフィールを使うか指定（下記）

同梱例：
- `market.json` … 日本株・AI半導体・為替（20:00 JST、本運用）
- `webdesign.json` … Webデザイン・フロントエンド（08:00 JST）※サンプル

## 実行

手動（Claude Code 内）:

> `/news market` … 調査して `message.txt` を生成 → `python send_line.py message.txt`

自動（毎日 20:00 JST・Windowsタスク）:

> `run_market_news.ps1 [profile]` が `claude -p "/news <profile>"` を headless 実行
> → `message.txt` 生成 → `send_line.py` で送信。ログは `logs/`。
> 既定プロフィールは `market`。

## 株YouTube銘柄メモ（youtube-stocks）

株取引YouTube動画の**字幕から銘柄と配信者の見立てを抽出**して LINE 送信する。

| ファイル | 役割 |
|---|---|
| `fetch_transcript.py` | 動画URL/IDの字幕を取得し `transcript.txt` に保存（`youtube-transcript-api`） |
| `.agents/skills/youtube-stocks/SKILL.md` | `/youtube-stocks` skill。`transcript.txt`→銘柄+見立て抽出→`message.txt` |
| `configs/youtube_stocks*.json` | 抽出ルール・出力体裁・監視チャンネル（チャンネルごとに1ファイル。**ここを編集**） |
| `run_youtube_stocks.ps1` | 字幕取得→`claude -p`→送信を通しで実行（要 動画URL引数。手動用） |
| `check_new_videos.py` | チャンネルRSSで新着検知（APIキー不要）。`--config` で対象プロフィールを切替、処理済みは設定の `state_file` で管理 |
| `run_youtube_watch.ps1` | 新着検知→未処理動画だけ取得→抽出→送信→記録（定期実行用）。`-Config` で監視プロフィールを切替 |

処理は **Pythonが字幕取得（確定処理）→ `claude -p` が抽出（LLM, sonnet）→ `send_line.py` が送信** に分離。

### セットアップ（初回のみ）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 実行

字幕取得だけ確認:

```powershell
.\.venv\Scripts\python.exe fetch_transcript.py "https://www.youtube.com/live/XXXXXXXXXXX" --out transcript.txt
```

通しで実行（取得→抽出→送信）:

```powershell
.\run_youtube_stocks.ps1 "https://www.youtube.com/live/XXXXXXXXXXX"
```

Claude Code 内で手動実行する場合は、先に `transcript.txt` を用意してから `/youtube-stocks`。

### 自動監視（チャンネル新着 → 自動配信）

プロフィール（`configs/youtube_stocks*.json`）の `channels[].channel_id` に監視対象を設定し、RSSフィード
（`https://www.youtube.com/feeds/videos.xml?channel_id=...`）で新着を検知する。**APIキー不要・クォータ消費ゼロ**。

チャンネル/状態ファイル/字幕ファイル/送信本文ファイルはすべて設定から読むため、`-Config` を変えるだけで
**複数チャンネルをそれぞれ別タスクで独立監視**できる（既定は Sho's投資情報局）。

初回だけ既存動画を基準化（過去動画の一括処理を防ぐ。プロフィールごとに実行）:

```powershell
.\.venv\Scripts\python.exe check_new_videos.py --init                                   # Sho's
.\.venv\Scripts\python.exe check_new_videos.py --init --config configs\youtube_stocks_kamioka.json  # 上岡
```

以降は定期実行。新着があれば 取得→抽出→送信→記録 まで自動:

```powershell
.\run_youtube_watch.ps1                                              # Sho's（既定）
.\run_youtube_watch.ps1 -Config configs\youtube_stocks_kamioka.json  # 上岡
.\run_youtube_watch.ps1 -Config configs\youtube_stocks_bitasen.json  # ビタセン
```

- 新着なし→何もせず正常終了。1回の処理上限は `watch.max_new_per_run`（既定3）。
- RSSは断続的に空応答を返すため `check_new_videos` 側でリトライ。取得全滅時は「新着なし」と区別してスキップ（次回再試行・取りこぼし防止）。
- 送信成功した動画だけ設定の `state_file`（既定 `processed_videos.json`）に記録するので、失敗は次回再試行される（`claude -p` がPro上限に当たって抽出失敗した時も同様に再試行）。

#### 監視プロフィール一覧

各チャンネルを別プロフィール（=別 config）として独立監視する。新規追加は config をコピーして
`channel_id` / `transcript_file` / `output_file` / `watch.state_file` を一意にし、専用タスクを登録するだけ。

| プロフィール | config | チャンネル | 重点 |
|---|---|---|---|
| Sho's（既定） | `youtube_stocks.json` | Sho's投資情報局 | 定期分析＋夜ライブ。種別自動判定（下記） |
| 上岡 | `youtube_stocks_kamioka.json` | 上岡正明 | その日の市場ニュース解説中心。雑談・宣伝は「与太話(一言)」に圧縮 |
| ビタセン | `youtube_stocks_bitasen.json` | ビタセン | 優待クロス・短期優待投資。権利月・在庫・取得コスト等の実務情報を厚く |

#### 種別の自動判定（定期/ライブ・Sho's専用）

Sho's は1日に2セッション（**夕方〜16:50の定期分析** と **夜22時のライブ**）あり、
アーカイブの公開時刻はバラバラ。skill が文字起こし冒頭から種別を判定し、出力の重点を変える
（`configs/youtube_stocks.json` の `video_types`）:
- **定期/全体**: 全体動向・マクロ・需給を厚く、個別銘柄は主要なものに絞る
- **ライブ/個別**: 個別銘柄を網羅

タイトル行先頭に `[定期/全体]` `[ライブ/個別]` を付ける。公開時刻で種別を撃ち分けられないため、
1日2回まわして新着を全部拾う方式（`max_new_per_run`=3、ID重複防止で二重送信なし）。

#### 定期実行（登録済み Windows タスク）

プロフィールごとに別タスクとして登録（`run_youtube_watch.ps1 -Config <設定>`）。
共通設定: StartWhenAvailable / ExecutionTimeLimit 1時間 / 多重起動は `.youtube_watch_<profile>.lock` で無視。

| タスク名 | スケジュール(JST) | プロフィール |
|---|---|---|
| `YouTubeStocksLINE_Watch` | 毎日 08:00 / 20:00 | Sho's（既定） |
| `YouTubeStocksLINE_Watch_Kamioka` | 毎日 11:30 | 上岡 |
| `YouTubeStocksLINE_Watch_Bitasen` | 毎日 20:30 | ビタセン |

```powershell
# 例（タスク名を差し替えて使う）
Get-ScheduledTask -TaskName YouTubeStocksLINE_Watch          # 状態確認
Disable-ScheduledTask -TaskName YouTubeStocksLINE_Watch      # 一時停止
Enable-ScheduledTask  -TaskName YouTubeStocksLINE_Watch      # 再開
Unregister-ScheduledTask -TaskName YouTubeStocksLINE_Watch -Confirm:$false  # 削除
```

### 注意

- `youtube-transcript-api` は**データセンターIPからブロックされる**ことがある（CI不可な場合あり）。ローカル実行推奨。
- **ライブ配信は字幕生成が遅れる/無い**ことがある。アーカイブ化後に取得する。
- 自動字幕は銘柄名・コードを誤変換するため、skill が文脈補正し、**口頭コードは信用せず**不確実なものは「要確認」に回す。
- チャンネル自動監視は **RSSフィード方式**（APIキー不要）。YouTube Data API は使わない。手動で個別URLを渡したい場合は `run_youtube_stocks.ps1 <動画URL>`。

## 認証情報

`.env` に2行を記入（値はコミットされない）:

```
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_USER_ID=...
MARKET_INFO_API_BASE_URL=https://...
MINI_TOOLS_BASE_URL=https://mini-tools-rho.vercel.app
```

## 株主優待変更の通知

初回は現在のイベントを通知済みにして、過去分の一括送信を防ぐ:

```powershell
python send_disclosure_events.py --init
```

送信せず本文だけ確認:

```powershell
python send_disclosure_events.py --dry-run
```

定期実行:

```powershell
.\run_disclosure_events.ps1
```

- `audience=all` の優待新設・拡充・変更・廃止・要確認を対象にする。
- 各イベントにmini-toolsの対象カードへ移動する確認URLを付ける。
- 送信成功後だけ `processed_disclosure_events.json` に記録する。
- 新着がなければ送信せず正常終了する。
- ランナーは2時間以内の多重起動をロックで回避し、ログを30日保持する。

## 送信

```
python send_line.py message.txt
```

失敗時は HTTP ステータスコードとレスポンス本文を stderr に出力し、終了コード 1。
ニュース取得に失敗した場合は取得できた範囲だけで生成する。
出典 URL が取れない情報は使わない。

## 運用（Windowsタスク）

- タスク名: `MarketNewsLINE_Daily`
- スケジュール: 毎日 20:00 JST（終了日なし・恒久）
- 実行: `run_market_news.ps1`（既定プロフィール `market`）
- ログ: `logs\run_YYYYMMDD_HHMMSS.log`

操作コマンド:

```powershell
# 状態確認
Get-ScheduledTask -TaskName MarketNewsLINE_Daily
Get-ScheduledTaskInfo -TaskName MarketNewsLINE_Daily

# 一時停止 / 再開
Disable-ScheduledTask -TaskName MarketNewsLINE_Daily
Enable-ScheduledTask  -TaskName MarketNewsLINE_Daily

# 完全削除
Unregister-ScheduledTask -TaskName MarketNewsLINE_Daily -Confirm:$false
```

PCがスリープ/オフだった日はスキップ（次回起動時の補完は `StartWhenAvailable` で多少カバー）。
