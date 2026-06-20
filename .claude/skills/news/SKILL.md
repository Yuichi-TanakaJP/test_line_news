---
name: news
description: 指定プロフィール(configs/<profile>.json)に従い最新ニュースを調査し、LINE送信用の本文を message.txt に生成する。市場メモなど毎日のニュースまとめに使う。引数でプロフィール名(例 market)を指定。
---

# news — config駆動ニュース調査 → message.txt 生成

リクエストされたプロフィール: **$ARGUMENTS**（未指定なら `market`）

以下を厳密に実行する。

1. `configs/<profile>.json` を読む（`<profile>` は上記引数。例: `configs/market.json`）。
   その `themes` / `priority_sources_A` / `priority_sources_B` / `rules` /
   `sections` / `impact_labels` / `format` / `title` に従う。
2. **実行日(JST)を確認**してから、WebSearch / WebFetch で最新ニュースを調査する。
   - **鮮度ルール（最重要・config.recency に従う）**
     - 採用は原則 **実行日(JST) と 前営業日** の発生分のみ
     - `recency.max_age_hours`(既定36h) より古いものは原則不採用
     - `recency.exclude_if_older_than_hours`(既定72h) より古いものは絶対不採用
     - 例外: 古い件でも「本日新展開（続報・新発表・新指標）」があれば採用可。
       その場合は **本日の新展開を本文の中心** にし、背景は1行以内
     - 検索クエリには **実行日(YYYY/MM/DD または "今日" "本日")** を含めて鮮度を上げる
     - WebFetchで日付が明示されないページは、別ソースで日付裏取りを試みる
   - 各ニュース見出しの末尾に **発生日 (MM/DD)** を必ず付ける
   - 一次情報・信頼できるソースを優先（priority_sources_A を優先）
   - 出典URLが取れない情報は使わない
   - 事実と推測を分ける。強い断定を避ける。投資助言にしない
   - 同じニュースは重複除去する
   - 影響は impact_labels のいずれかで分類する
3. `format` に従い、人間が読みやすい日本語テキストで本文を作る。
   - 1行目は `title`、2行目に **実行日(JST, YYYY/MM/DD(曜))** と直近取引日
   - 各セクションは見出し行 `format.section_header_prefix + "N. セクション名"`
     で始める（罫線は使わない）
   - 各ニュース項目の見出し末尾に **(MM/DD)** を付け、本日分は **(MM/DD・本日)** と明示
   - 全体 `format.max_chars` 文字以内
   - 末尾に `format.footer` を入れる
4. 完成した本文を **`message.txt` に上書き保存**する（このファイルのみを書く）。
   送信はしない（送信は呼び出し側スクリプト `line_news.line` が行う）。
5. ニュース取得に失敗した場合は、取得できた範囲だけで `message.txt` を生成する。

出力は `message.txt` のみ。余計な説明や他ファイルの変更はしないこと。
