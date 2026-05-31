# 毎日ニュースメモ → LINE 送信ツール（汎用）

設定ファイル（プロフィール）を差し替えるだけで、ジャンルを変えて使える
「毎日リサーチ → LINE 送信」ツール。本運用中（毎日 20:00 JST）。

2系統のパイプラインを同居:
- **news** … Web調査ベースの毎日ニュースメモ（`/news` skill）
- **youtube-stocks** … 株YouTube動画の字幕から銘柄＋見立てを抽出（`/youtube-stocks` skill）

どちらも「LLMで本文生成 → `message.txt` → `send_line.py` で送信」を共有する。

## 構成

| ファイル | 役割 |
|---|---|
| `.claude/skills/news/SKILL.md` | `/news <profile>` skill。調査〜`message.txt`生成の指示本体 |
| `configs/*.json` | プロフィール。テーマ・優先ソース・出力構成を定義（**ここを編集して方向性を変える**） |
| `send_line.py` | LINE Messaging API push 送信。`.env` または環境変数から認証情報を読む |
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
| `.claude/skills/youtube-stocks/SKILL.md` | `/youtube-stocks` skill。`transcript.txt`→銘柄+見立て抽出→`message.txt` |
| `configs/youtube_stocks.json` | 抽出ルール・出力体裁・監視チャンネル（**ここを編集**） |
| `run_youtube_stocks.ps1` | 字幕取得→`claude -p`→送信を通しで実行（要 動画URL引数） |

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

### 注意

- `youtube-transcript-api` は**データセンターIPからブロックされる**ことがある（CI不可な場合あり）。ローカル実行推奨。
- **ライブ配信は字幕生成が遅れる/無い**ことがある。アーカイブ化後に取得する。
- 自動字幕は銘柄名・コードを誤変換するため、skill が文脈補正し、**口頭コードは信用せず**不確実なものは「要確認」に回す。
- チャンネル自動監視（YouTube Data API）は未実装。当面は動画URLを手動で渡す運用。

## 認証情報

`.env` に2行を記入（値はコミットされない）:

```
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_USER_ID=...
```

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
