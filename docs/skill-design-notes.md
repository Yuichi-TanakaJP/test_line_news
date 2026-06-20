# Skill と Script の設計メモ

このプロジェクトで `/news` を **project skill** にした経緯と判断を残す。

## 用語の関係

| 要素 | 役割 | 個数 |
|---|---|---|
| Skill (`/news`) | やり方（手順・ロジック）。「configを読む→調査→`message.txt`生成」 | 1個 |
| config (`configs/*.json`) | 何を・どこから・どう（データ）。テーマ・優先ソース・出力構成 | ジャンルごと複数 |
| Script (`run_market_news.ps1`) | オーケストレーター。Skill起動と送信・ログ・スケジュール連携 | 1個 |

料理の比喩：Skill＝手順書、config＝食材リスト、`/news market`＝「marketの食材で手順を実行」。

## config の選び方

選択軸は **`/news` に渡すプロフィール名 = configファイル名** に統一。

- 手動: `/news market`（引数なしは既定 `market`）→ `configs/market.json`
- 自動: `run_market_news.ps1 [profile]` の第1引数（既定 `market`）
- 追加: `configs/<新名>.json` を作れば `/news <新名>` で選択可能
- 複数ジャンルを別時刻配信: タスクを分け、各々に引数を渡して登録

SKILL.md 内で `configs/<引数>.json` を読む設計のため、引数変更＝読むconfig変更。

## なぜ Script ⊃ Skill にしたか（設計判断）

一般には Skill がスクリプトを同梱する「大きい括り」も可能。今回はあえて
Script をオーケストレーターにし、Skill は「調査＆原稿生成」の1工程のみ担当。

```
run_market_news.ps1（外側）
  ├─ claude -p "/news market"   ← Skill: 調査して message.txt 生成のみ
  └─ python -m line_news.line   ← 送信は Skill の外（決定的）
```

理由：

| 観点 | 内容 |
|---|---|
| 送信の確実性 | LINE送信はAIに任せずPython固定。失敗時のHTTPコード/本文ログが安定 |
| 権限の最小化 | Skill実行時の claude に Bash/送信権限を与えず、調査系ツールのみ許可 |
| 関心の分離 | 「何を書くか(Skill)」と「どう届けるか(Script)」を分離。送信先変更にSkill不変 |

### 代替案（採用せず）
SKILL.md に送信まで書き claude に Bash 許可すれば Skill が完結し ps1 不要に。
ただし送信堅牢性が下がり権限が広がるため、トライアルでは現状維持を選択。

## Skill化の価値（正直な評価）

効く場面：
- ◎ 手動でサッと実行（`/news market` だけで最新版生成）
- ○ 指示の一元管理(DRY)・保守性
- ○ プロフィール引数で多ジャンル再利用

効きが小さい場面：
- 自動トライアルだけが目的なら、単なるプロンプトファイルでも動作は同じ。
  Skill化の純粋な追加価値は「手動 `/news` が使える」「保守がきれい」の2点で、
  自動配信の品質向上ではない。

結論：手動利用や多ジャンル展開・継続的なルール調整をするなら明確に有効。
しなくてもコスト増なしで選択肢が増えただけなので保持して損はない。

## 関連ファイル

- `.claude/skills/news/SKILL.md` — 手順本体
- `configs/*.json` — プロフィール
- `run_market_news.ps1` — オーケストレーター
- `src/line_news/line.py`（`python -m line_news.line`）— LINE送信（決定的）
- `README.md` — 使い方
