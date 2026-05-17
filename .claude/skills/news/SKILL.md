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
2. WebSearch / WebFetch で最新ニュースを調査する。
   - 一次情報・信頼できるソースを優先（priority_sources_A を優先）
   - 出典URLが取れない情報は使わない
   - 事実と推測を分ける。強い断定を避ける。投資助言にしない
   - 同じニュースは重複除去する
   - 影響は impact_labels のいずれかで分類する
3. `format` に従い、人間が読みやすい日本語テキストで本文を作る。
   - 1行目は `title`、2行目に日付(JST)と直近取引日
   - 各セクションは見出し行 `format.section_header_prefix + "N. セクション名"`
     で始める（罫線は使わない）
   - 全体 `format.max_chars` 文字以内
   - 末尾に `format.footer` を入れる
4. 完成した本文を **`message.txt` に上書き保存**する（このファイルのみを書く）。
   送信はしない（送信は呼び出し側スクリプト `send_line.py` が行う）。
5. ニュース取得に失敗した場合は、取得できた範囲だけで `message.txt` を生成する。

出力は `message.txt` のみ。余計な説明や他ファイルの変更はしないこと。
